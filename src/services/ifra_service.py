"""IFRA compliance service.

Supports checking both directly added ingredients and incidentals
from natural materials per IFRA Annex IV (Transparency List).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

from ..models.regulatory import (
    Market,
    ProductType,
    ComplianceStatus,
    ComplianceResult,
    PRODUCT_TO_IFRA_CATEGORY,
)
from ..models.naturals import IncidentalReport
from ..integrations.aroma_lab import (
    AromaLabClient,
    FormulaData,
    IFRACategory,
    IFRARestriction,
    RestrictionType,
)
from .naturals_service import NaturalsService


@dataclass
class IFRAComplianceResult:
    """Detailed IFRA compliance result."""
    is_compliant: bool
    violations: list[ComplianceResult]
    warnings: list[ComplianceResult]
    compliant_ingredients: list[str]
    certificate_number: Optional[str] = None
    amendment_version: str = "51st"
    # Incidentals tracking
    incidental_reports: list[IncidentalReport] = field(default_factory=list)
    incidental_totals: dict[str, float] = field(default_factory=dict)


class IFRAService:
    """Service for IFRA compliance checking and certificate generation.

    Properly accounts for incidentals (restricted substances naturally
    present in essential oils and other natural materials) per IFRA
    Annex IV / Transparency List.
    """

    def __init__(
        self,
        aroma_lab_client: Optional[AromaLabClient] = None,
        naturals_service: Optional[NaturalsService] = None,
    ):
        """Initialize the service.

        Args:
            aroma_lab_client: Client for aroma-lab data. Creates one if not provided.
            naturals_service: Service for natural material data. Creates one if not provided.
        """
        self.client = aroma_lab_client or AromaLabClient()
        self.naturals_service = naturals_service or NaturalsService()

    def get_ifra_category(self, product_type: ProductType) -> Optional[str]:
        """Get IFRA category string for a product type.

        Args:
            product_type: The product type.

        Returns:
            IFRA category string like "4" or "5A".
        """
        return PRODUCT_TO_IFRA_CATEGORY.get(product_type)

    def check_compliance(
        self,
        formula: FormulaData,
        product_type: ProductType,
        fragrance_concentration: float = 100.0,
        include_incidentals: bool = True,
    ) -> IFRAComplianceResult:
        """Check formula for IFRA compliance.

        Properly accounts for incidentals from natural materials when
        include_incidentals is True. The total of each restricted substance
        is calculated as: directly added + incidentals from naturals.

        Args:
            formula: Formula to check.
            product_type: Product type for category determination.
            fragrance_concentration: Fragrance % in final product (for dilution).
            include_incidentals: If True, include incidentals from natural materials.

        Returns:
            IFRAComplianceResult with detailed results.
        """
        category_str = self.get_ifra_category(product_type)
        if not category_str:
            # Product type not mapped to IFRA category
            return IFRAComplianceResult(
                is_compliant=True,
                violations=[],
                warnings=[],
                compliant_ingredients=[ing.name for ing in formula.ingredients],
            )

        # Get the IFRACategory enum
        category = self._get_category_enum(category_str)
        if not category:
            return IFRAComplianceResult(
                is_compliant=True,
                violations=[],
                warnings=[],
                compliant_ingredients=[ing.name for ing in formula.ingredients],
            )

        # Calculate incidentals from natural materials
        incidental_totals: dict[str, float] = {}
        incidental_reports: list[IncidentalReport] = []
        if include_incidentals:
            incidental_totals, incidental_reports = self.naturals_service.calculate_incidentals(formula)

        violations: list[ComplianceResult] = []
        warnings: list[ComplianceResult] = []
        compliant: list[str] = []

        # Track which restricted substances we've already checked (for aggregation)
        checked_restricted: set[str] = set()

        # First pass: check directly added ingredients
        for ingredient in formula.ingredients:
            # Skip natural materials - their restricted content is handled via incidentals
            if self.naturals_service.is_natural(ingredient.cas_number):
                compliant.append(ingredient.name)
                continue

            restriction = self.client.get_ifra_restriction(ingredient.cas_number)

            if restriction is None:
                # Not restricted
                compliant.append(ingredient.name)
                continue

            checked_restricted.add(ingredient.cas_number)

            # Calculate actual concentration: direct + incidentals
            direct_conc = ingredient.percentage
            incidental_conc = incidental_totals.get(ingredient.cas_number, 0.0)
            total_conc = direct_conc + incidental_conc
            actual_conc = total_conc * (fragrance_concentration / 100.0)

            limit = restriction.get_limit_for_category(category)

            # Build details string
            if incidental_conc > 0:
                details_prefix = f"{ingredient.name}: {direct_conc:.4f}% direct + {incidental_conc:.4f}% incidentals = {total_conc:.4f}%"
            else:
                details_prefix = f"{ingredient.name}"

            if restriction.restriction_type == RestrictionType.PROHIBITION:
                violations.append(
                    ComplianceResult(
                        requirement=f"IFRA Category {category_str} - Prohibited",
                        status=ComplianceStatus.NON_COMPLIANT,
                        market=Market.US,  # IFRA is global
                        details=f"{details_prefix} is prohibited under IFRA {restriction.amendment_number or '51st'} Amendment",
                        cas_number=ingredient.cas_number,
                        ingredient_name=ingredient.name,
                        current_value=actual_conc,
                        limit_value=0.0,
                        regulation_reference=f"IFRA {restriction.amendment_number or '51st'} Amendment",
                    )
                )
            elif limit is not None:
                if actual_conc > limit:
                    violations.append(
                        ComplianceResult(
                            requirement=f"IFRA Category {category_str} - Max {limit}%",
                            status=ComplianceStatus.NON_COMPLIANT,
                            market=Market.US,
                            details=f"{details_prefix} at {actual_conc:.4f}% exceeds limit of {limit}%",
                            cas_number=ingredient.cas_number,
                            ingredient_name=ingredient.name,
                            current_value=actual_conc,
                            limit_value=limit,
                            regulation_reference=f"IFRA {restriction.amendment_number or '51st'} Amendment",
                        )
                    )
                elif actual_conc > limit * 0.9:
                    # Warning if within 10% of limit
                    warnings.append(
                        ComplianceResult(
                            requirement=f"IFRA Category {category_str} - Max {limit}%",
                            status=ComplianceStatus.WARNING,
                            market=Market.US,
                            details=f"{details_prefix} at {actual_conc:.4f}% is approaching limit of {limit}%",
                            cas_number=ingredient.cas_number,
                            ingredient_name=ingredient.name,
                            current_value=actual_conc,
                            limit_value=limit,
                            regulation_reference=f"IFRA {restriction.amendment_number or '51st'} Amendment",
                        )
                    )
                    compliant.append(ingredient.name)
                else:
                    compliant.append(ingredient.name)
            else:
                compliant.append(ingredient.name)

        # Second pass: check incidentals that weren't directly added
        for cas_number, incidental_conc in incidental_totals.items():
            if cas_number in checked_restricted:
                continue  # Already checked above

            restriction = self.client.get_ifra_restriction(cas_number)
            if restriction is None:
                continue

            actual_conc = incidental_conc * (fragrance_concentration / 100.0)
            limit = restriction.get_limit_for_category(category)

            # Get name for this restricted substance
            name = restriction.name

            if restriction.restriction_type == RestrictionType.PROHIBITION:
                violations.append(
                    ComplianceResult(
                        requirement=f"IFRA Category {category_str} - Prohibited (incidental)",
                        status=ComplianceStatus.NON_COMPLIANT,
                        market=Market.US,
                        details=f"{name} ({incidental_conc:.4f}% from natural materials) is prohibited",
                        cas_number=cas_number,
                        ingredient_name=f"{name} (incidental)",
                        current_value=actual_conc,
                        limit_value=0.0,
                        regulation_reference=f"IFRA {restriction.amendment_number or '51st'} Amendment",
                    )
                )
            elif limit is not None:
                if actual_conc > limit:
                    violations.append(
                        ComplianceResult(
                            requirement=f"IFRA Category {category_str} - Max {limit}% (incidental)",
                            status=ComplianceStatus.NON_COMPLIANT,
                            market=Market.US,
                            details=f"{name} at {actual_conc:.4f}% (from natural materials) exceeds limit of {limit}%",
                            cas_number=cas_number,
                            ingredient_name=f"{name} (incidental)",
                            current_value=actual_conc,
                            limit_value=limit,
                            regulation_reference=f"IFRA {restriction.amendment_number or '51st'} Amendment",
                        )
                    )
                elif actual_conc > limit * 0.9:
                    warnings.append(
                        ComplianceResult(
                            requirement=f"IFRA Category {category_str} - Max {limit}% (incidental)",
                            status=ComplianceStatus.WARNING,
                            market=Market.US,
                            details=f"{name} at {actual_conc:.4f}% (from natural materials) is approaching limit of {limit}%",
                            cas_number=cas_number,
                            ingredient_name=f"{name} (incidental)",
                            current_value=actual_conc,
                            limit_value=limit,
                            regulation_reference=f"IFRA {restriction.amendment_number or '51st'} Amendment",
                        )
                    )

        is_compliant = len(violations) == 0
        certificate_number = None
        if is_compliant:
            certificate_number = self._generate_certificate_number()

        return IFRAComplianceResult(
            is_compliant=is_compliant,
            violations=violations,
            warnings=warnings,
            compliant_ingredients=compliant,
            certificate_number=certificate_number,
            incidental_reports=incidental_reports,
            incidental_totals=incidental_totals,
        )

    def _get_category_enum(self, category_str: str) -> Optional[IFRACategory]:
        """Convert category string to enum."""
        for cat in IFRACategory:
            if cat.value == category_str:
                return cat
        return None

    def _generate_certificate_number(self) -> str:
        """Generate a unique certificate number."""
        timestamp = datetime.now().strftime("%Y%m%d")
        unique_id = uuid4().hex[:8].upper()
        return f"IFRA-{timestamp}-{unique_id}"

    def get_category_limits(self, cas_number: str) -> dict[str, Optional[float]]:
        """Get all category limits for an ingredient.

        Args:
            cas_number: CAS registry number.

        Returns:
            Dictionary mapping category strings to limits.
        """
        restriction = self.client.get_ifra_restriction(cas_number)
        if not restriction:
            return {}

        limits = {}
        for category in IFRACategory:
            limit = restriction.get_limit_for_category(category)
            limits[category.value] = limit

        return limits
