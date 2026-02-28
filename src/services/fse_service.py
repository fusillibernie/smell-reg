"""Fragrance Safety Evaluation (FSE) service."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from ..models.fse import (
    FSEEndpoint,
    RiskLevel,
    EndpointAssessment,
    IngredientFSE,
    FSEReport,
    EXPOSURE_PARAMETERS,
)
from ..models.regulatory import ProductType
from ..integrations.aroma_lab import FormulaData, AromaLabClient


class FSEService:
    """Service for generating Fragrance Safety Evaluations."""

    def __init__(
        self,
        aroma_lab_client: Optional[AromaLabClient] = None,
        data_dir: Optional[Path] = None,
    ):
        """Initialize the service.

        Args:
            aroma_lab_client: Client for aroma-lab safety data.
            data_dir: Directory containing regulatory data files.
        """
        self.client = aroma_lab_client or AromaLabClient()
        self._data_dir = data_dir or Path(__file__).parent.parent.parent / "data" / "regulatory"
        self._toxicity_data: dict = {}
        self._load_toxicity_data()

    def _load_toxicity_data(self) -> None:
        """Load toxicological data from JSON file."""
        toxicity_file = self._data_dir / "toxicity_data.json"
        if toxicity_file.exists():
            try:
                with open(toxicity_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._toxicity_data = data.get("ingredients", {})
            except Exception as e:
                print(f"Warning: Failed to load toxicity data: {e}")

    def generate_fse(
        self,
        formula: FormulaData,
        product_type: ProductType,
        fragrance_concentration: float,
        intended_use: str = "",
        assessor: Optional[str] = None,
    ) -> FSEReport:
        """Generate a Fragrance Safety Evaluation.

        Args:
            formula: Formula to evaluate.
            product_type: Product type.
            fragrance_concentration: Fragrance % in final product.
            intended_use: Description of intended use.
            assessor: Name of assessor.

        Returns:
            FSEReport with safety evaluation.
        """
        # Get exposure parameters
        product_key = product_type.value
        exposure = EXPOSURE_PARAMETERS.get(product_key, {})

        # Evaluate each ingredient
        ingredients: list[IngredientFSE] = []
        for ing in formula.ingredients:
            ing_fse = self._evaluate_ingredient(
                cas_number=ing.cas_number,
                name=ing.name,
                concentration=ing.percentage * (fragrance_concentration / 100.0),
            )
            ingredients.append(ing_fse)

        # Aggregate endpoint summaries
        endpoint_summaries = self._aggregate_endpoints(ingredients)

        # Generate overall conclusion
        conclusion = self._generate_conclusion(endpoint_summaries)

        return FSEReport(
            formula_name=formula.name,
            product_type=product_type.value,
            intended_use=intended_use or f"Use in {product_type.value.replace('_', ' ')}",
            fragrance_concentration=fragrance_concentration,
            exposure_area_cm2=exposure.get("exposure_area_cm2"),
            applications_per_day=exposure.get("applications_per_day", 1.0),
            retention_factor=exposure.get("retention_factor", 1.0),
            ingredients=ingredients,
            endpoint_summaries=endpoint_summaries,
            assessor=assessor,
            assessment_date=datetime.now(),
            report_number=self._generate_report_number(),
            overall_conclusion=conclusion,
        )

    def _evaluate_ingredient(
        self,
        cas_number: str,
        name: str,
        concentration: float,
    ) -> IngredientFSE:
        """Evaluate a single ingredient for all endpoints.

        Args:
            cas_number: CAS registry number.
            name: Ingredient name.
            concentration: Concentration in final product (%).

        Returns:
            IngredientFSE with assessments.
        """
        assessments: list[EndpointAssessment] = []

        # Get safety data from aroma-lab if available
        restriction = self.client.get_ifra_restriction(cas_number)
        has_rifm = restriction is not None

        # Evaluate each endpoint
        for endpoint in FSEEndpoint:
            assessment = self._assess_endpoint(
                endpoint=endpoint,
                cas_number=cas_number,
                concentration=concentration,
                restriction=restriction,
            )
            assessments.append(assessment)

        return IngredientFSE(
            cas_number=cas_number,
            name=name,
            concentration_percent=concentration,
            assessments=assessments,
            rifm_data_available=has_rifm,
            qsar_data_available=False,  # Would require QSAR integration
        )

    def _assess_endpoint(
        self,
        endpoint: FSEEndpoint,
        cas_number: str,
        concentration: float,
        restriction=None,
    ) -> EndpointAssessment:
        """Assess a single toxicological endpoint.

        Args:
            endpoint: The endpoint to assess.
            cas_number: CAS registry number.
            concentration: Concentration in product.
            restriction: IFRA restriction data if available.

        Returns:
            EndpointAssessment result.
        """
        endpoint_key = endpoint.value

        # Check toxicity database first
        if cas_number in self._toxicity_data:
            tox_data = self._toxicity_data[cas_number]
            endpoint_data = tox_data.get("endpoints", {}).get(endpoint_key, {})

            if endpoint_data:
                return self._assess_from_toxicity_data(
                    endpoint, concentration, endpoint_data, tox_data.get("name", cas_number)
                )

        # Fall back to IFRA data
        if restriction is not None:
            return self._assess_from_ifra_data(endpoint, concentration, restriction)

        # No data available
        return EndpointAssessment(
            endpoint=endpoint,
            risk_level=RiskLevel.INSUFFICIENT_DATA,
            exposure_level=concentration,
            data_source="No toxicological data available",
            notes="Safety assessment requires additional data",
        )

    def _assess_from_toxicity_data(
        self,
        endpoint: FSEEndpoint,
        concentration: float,
        endpoint_data: dict,
        ingredient_name: str,
    ) -> EndpointAssessment:
        """Assess endpoint using toxicity database data.

        Args:
            endpoint: The endpoint to assess.
            concentration: Concentration in product.
            endpoint_data: Endpoint-specific toxicity data.
            ingredient_name: Name of the ingredient.

        Returns:
            EndpointAssessment result.
        """
        risk_str = endpoint_data.get("risk", "insufficient_data")
        notes = endpoint_data.get("notes", "")

        # Map string risk to RiskLevel enum
        risk_map = {
            "safe": RiskLevel.SAFE,
            "acceptable": RiskLevel.ACCEPTABLE,
            "caution": RiskLevel.CAUTION,
            "unacceptable": RiskLevel.UNACCEPTABLE,
            "insufficient_data": RiskLevel.INSUFFICIENT_DATA,
        }
        base_risk = risk_map.get(risk_str, RiskLevel.INSUFFICIENT_DATA)

        # For sensitization, check concentration against NESIL
        if endpoint == FSEEndpoint.SKIN_SENSITIZATION:
            nesil = endpoint_data.get("nesil_percent")
            if nesil is not None and concentration > 0:
                # Calculate if within limit
                if concentration > nesil:
                    return EndpointAssessment(
                        endpoint=endpoint,
                        risk_level=RiskLevel.UNACCEPTABLE,
                        exposure_level=concentration,
                        threshold=nesil,
                        margin_of_safety=nesil / concentration,
                        data_source="Toxicity Database (RIFM/SCCS)",
                        notes=f"Exceeds NESIL of {nesil}%. {notes}",
                    )
                elif concentration > nesil * 0.8:
                    return EndpointAssessment(
                        endpoint=endpoint,
                        risk_level=RiskLevel.CAUTION,
                        exposure_level=concentration,
                        threshold=nesil,
                        margin_of_safety=nesil / concentration,
                        data_source="Toxicity Database (RIFM/SCCS)",
                        notes=f"Approaching NESIL of {nesil}%. {notes}",
                    )

        # For irritation, check concentration threshold
        if endpoint == FSEEndpoint.SKIN_IRRITATION:
            threshold = endpoint_data.get("threshold_percent")
            if threshold is not None and concentration > threshold:
                return EndpointAssessment(
                    endpoint=endpoint,
                    risk_level=RiskLevel.CAUTION,
                    exposure_level=concentration,
                    threshold=threshold,
                    data_source="Toxicity Database",
                    notes=f"Above irritation threshold of {threshold}%. {notes}",
                )

        return EndpointAssessment(
            endpoint=endpoint,
            risk_level=base_risk,
            exposure_level=concentration,
            data_source="Toxicity Database (RIFM/SCCS/CIR)",
            notes=notes,
        )

    def _assess_from_ifra_data(
        self,
        endpoint: FSEEndpoint,
        concentration: float,
        restriction,
    ) -> EndpointAssessment:
        """Assess endpoint using IFRA restriction data.

        Args:
            endpoint: The endpoint to assess.
            concentration: Concentration in product.
            restriction: IFRA restriction data.

        Returns:
            EndpointAssessment result.
        """
        from ..integrations.aroma_lab import RestrictionType

        # Skin sensitization - use IFRA limit
        if endpoint == FSEEndpoint.SKIN_SENSITIZATION:
            if restriction.restriction_type == RestrictionType.SENSITIZATION:
                limit = restriction.general_limit
                if limit and concentration <= limit:
                    return EndpointAssessment(
                        endpoint=endpoint,
                        risk_level=RiskLevel.ACCEPTABLE,
                        exposure_level=concentration,
                        threshold=limit,
                        margin_of_safety=limit / concentration if concentration > 0 else float('inf'),
                        data_source="RIFM/IFRA",
                        notes=f"Within IFRA limit of {limit}%",
                    )
                elif limit:
                    return EndpointAssessment(
                        endpoint=endpoint,
                        risk_level=RiskLevel.UNACCEPTABLE,
                        exposure_level=concentration,
                        threshold=limit,
                        margin_of_safety=limit / concentration if concentration > 0 else 0,
                        data_source="RIFM/IFRA",
                        notes=f"Exceeds IFRA limit of {limit}%",
                    )

        # Phototoxicity - check IFRA restriction type
        if endpoint == FSEEndpoint.PHOTOTOXICITY:
            if restriction.restriction_type == RestrictionType.PHOTOTOXICITY:
                limit = restriction.general_limit
                if limit and concentration > limit:
                    return EndpointAssessment(
                        endpoint=endpoint,
                        risk_level=RiskLevel.UNACCEPTABLE,
                        exposure_level=concentration,
                        threshold=limit,
                        data_source="RIFM/IFRA",
                        notes=f"Phototoxic - exceeds IFRA limit of {limit}%",
                    )

        # For other endpoints with IFRA data, assume acceptable if not specifically restricted
        return EndpointAssessment(
            endpoint=endpoint,
            risk_level=RiskLevel.SAFE,
            exposure_level=concentration,
            data_source="RIFM/IFRA - no specific concern for this endpoint",
        )

    def _aggregate_endpoints(
        self,
        ingredients: list[IngredientFSE],
    ) -> dict[str, RiskLevel]:
        """Aggregate endpoint assessments across all ingredients.

        Args:
            ingredients: List of ingredient FSE assessments.

        Returns:
            Dictionary mapping endpoint names to overall risk levels.
        """
        summaries: dict[str, RiskLevel] = {}

        for endpoint in FSEEndpoint:
            # Get worst-case risk for this endpoint
            risk_priority = [
                RiskLevel.UNACCEPTABLE,
                RiskLevel.INSUFFICIENT_DATA,
                RiskLevel.CAUTION,
                RiskLevel.ACCEPTABLE,
                RiskLevel.SAFE,
            ]

            worst_risk = RiskLevel.SAFE
            for ing in ingredients:
                for assess in ing.assessments:
                    if assess.endpoint == endpoint:
                        if risk_priority.index(assess.risk_level) < risk_priority.index(worst_risk):
                            worst_risk = assess.risk_level

            summaries[endpoint.value] = worst_risk

        return summaries

    def _generate_conclusion(self, summaries: dict[str, RiskLevel]) -> str:
        """Generate overall conclusion text.

        Args:
            summaries: Endpoint summary risk levels.

        Returns:
            Conclusion text.
        """
        has_unacceptable = RiskLevel.UNACCEPTABLE in summaries.values()
        has_insufficient = RiskLevel.INSUFFICIENT_DATA in summaries.values()
        has_caution = RiskLevel.CAUTION in summaries.values()

        if has_unacceptable:
            return (
                "This fragrance composition contains ingredients that exceed acceptable "
                "safety limits and requires reformulation before use."
            )
        elif has_insufficient:
            return (
                "This fragrance composition contains ingredients with insufficient safety data. "
                "Additional toxicological assessment is recommended before use."
            )
        elif has_caution:
            return (
                "This fragrance composition is acceptable for use with caution. "
                "Some ingredients are approaching safety limits."
            )
        else:
            return (
                "This fragrance composition has been evaluated and is considered safe "
                "for use in the intended product application."
            )

    def _generate_report_number(self) -> str:
        """Generate a unique FSE report number."""
        timestamp = datetime.now().strftime("%Y%m%d")
        unique_id = uuid4().hex[:8].upper()
        return f"FSE-{timestamp}-{unique_id}"
