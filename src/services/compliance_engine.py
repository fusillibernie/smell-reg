"""Main compliance engine orchestrating all compliance checks."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from ..models.regulatory import (
    Market,
    ProductType,
    ComplianceStatus,
    ComplianceResult,
    ComplianceReport,
)
from ..models.allergen import AllergenReport
from ..models.voc import VOCReport
from ..models.fse import FSEReport
from ..integrations.aroma_lab import FormulaData, AromaLabClient

from .ifra_service import IFRAService, IFRAComplianceResult
from .allergen_service import AllergenService
from .voc_service import VOCService
from .fse_service import FSEService
from .market_service import MarketService
from .formaldehyde_service import FormaldehydeService


class ComplianceEngine:
    """Main orchestrator for regulatory compliance checking."""

    def __init__(
        self,
        aroma_lab_client: Optional[AromaLabClient] = None,
        ifra_service: Optional[IFRAService] = None,
        allergen_service: Optional[AllergenService] = None,
        voc_service: Optional[VOCService] = None,
        fse_service: Optional[FSEService] = None,
        market_service: Optional[MarketService] = None,
        formaldehyde_service: Optional[FormaldehydeService] = None,
    ):
        """Initialize the compliance engine.

        Args:
            aroma_lab_client: Client for aroma-lab data.
            ifra_service: IFRA compliance service.
            allergen_service: Allergen detection service.
            voc_service: VOC calculation service.
            fse_service: FSE generation service.
            market_service: Market-specific requirements service.
            formaldehyde_service: Formaldehyde donor detection service.
        """
        self.client = aroma_lab_client or AromaLabClient()
        self.ifra_service = ifra_service or IFRAService(self.client)
        self.allergen_service = allergen_service or AllergenService()
        self.voc_service = voc_service or VOCService()
        self.fse_service = fse_service or FSEService(self.client)
        self.market_service = market_service or MarketService()
        self.formaldehyde_service = formaldehyde_service or FormaldehydeService()

    def check_compliance(
        self,
        formula: FormulaData,
        product_type: ProductType,
        markets: list[Market],
        fragrance_concentration: float = 100.0,
        is_leave_on: bool = True,
    ) -> ComplianceReport:
        """Run full compliance check across all services.

        Args:
            formula: Formula to check.
            product_type: Product type.
            markets: Target markets.
            fragrance_concentration: Fragrance % in final product.
            is_leave_on: True for leave-on products, False for rinse-off.

        Returns:
            ComplianceReport with all results.
        """
        all_results: list[ComplianceResult] = []

        # IFRA compliance check
        ifra_result = self.ifra_service.check_compliance(
            formula=formula,
            product_type=product_type,
            fragrance_concentration=fragrance_concentration,
        )
        all_results.extend(ifra_result.violations)
        all_results.extend(ifra_result.warnings)

        # Add compliant IFRA results for completeness
        for name in ifra_result.compliant_ingredients:
            all_results.append(
                ComplianceResult(
                    requirement="IFRA Compliance",
                    status=ComplianceStatus.COMPLIANT,
                    market=Market.US,  # IFRA is global
                    ingredient_name=name,
                )
            )

        # Allergen check
        allergen_report = self.allergen_service.check_formula(
            formula=formula,
            markets=markets,
            fragrance_concentration=fragrance_concentration,
            is_leave_on=is_leave_on,
        )
        for allergen in allergen_report.disclosure_required:
            all_results.append(
                ComplianceResult(
                    requirement="Allergen Disclosure Required",
                    status=ComplianceStatus.WARNING,
                    market=Market.EU,  # Primary market for allergen disclosure
                    details=f"{allergen.name} requires disclosure at {allergen.concentration_in_product:.4f}%",
                    cas_number=allergen.cas_number,
                    ingredient_name=allergen.name,
                    current_value=allergen.concentration_in_product,
                    limit_value=allergen.threshold,
                    regulation_reference="EC 1223/2009",
                )
            )

        # VOC check
        voc_report = self.voc_service.check_formula(
            formula=formula,
            product_type=product_type,
            markets=markets,
        )
        for calc in voc_report.calculations:
            status = ComplianceStatus.COMPLIANT if calc.is_compliant else ComplianceStatus.NON_COMPLIANT
            market = Market.US if calc.regulation.value == "carb" else Market.CA
            all_results.append(
                ComplianceResult(
                    requirement=f"VOC {calc.regulation.value.upper()} Limit",
                    status=status,
                    market=market,
                    details=f"VOC content {calc.total_voc_percent:.2f}% vs limit {calc.limit_percent:.2f}%",
                    current_value=calc.total_voc_percent,
                    limit_value=calc.limit_percent,
                    regulation_reference=f"{calc.regulation.value.upper()} VOC Regulations",
                )
            )

        # Market-specific requirements
        market_results = self.market_service.check_market_requirements(
            formula=formula,
            markets=markets,
            product_type=product_type,
            fragrance_concentration=fragrance_concentration,
        )
        all_results.extend(market_results)

        # Formaldehyde donor check
        formaldehyde_results = self.formaldehyde_service.get_compliance_results(
            formula=formula,
            markets=markets,
            fragrance_concentration=fragrance_concentration,
        )
        all_results.extend(formaldehyde_results)

        # Generate report
        certificate_number = None
        if all(
            r.status in (ComplianceStatus.COMPLIANT, ComplianceStatus.WARNING, ComplianceStatus.NOT_APPLICABLE)
            for r in all_results
        ):
            certificate_number = self._generate_certificate_number()

        return ComplianceReport(
            formula_name=formula.name,
            product_type=product_type,
            markets=markets,
            fragrance_concentration=fragrance_concentration,
            results=all_results,
            generated_at=datetime.now(),
            certificate_number=certificate_number,
        )

    def check_ifra(
        self,
        formula: FormulaData,
        product_type: ProductType,
        fragrance_concentration: float = 100.0,
    ) -> IFRAComplianceResult:
        """Run IFRA-only compliance check.

        Args:
            formula: Formula to check.
            product_type: Product type.
            fragrance_concentration: Fragrance % in final product.

        Returns:
            IFRAComplianceResult.
        """
        return self.ifra_service.check_compliance(
            formula=formula,
            product_type=product_type,
            fragrance_concentration=fragrance_concentration,
        )

    def check_allergens(
        self,
        formula: FormulaData,
        markets: list[Market],
        fragrance_concentration: float = 100.0,
        is_leave_on: bool = True,
    ) -> AllergenReport:
        """Run allergen-only check.

        Args:
            formula: Formula to check.
            markets: Target markets.
            fragrance_concentration: Fragrance % in final product.
            is_leave_on: True for leave-on products.

        Returns:
            AllergenReport.
        """
        return self.allergen_service.check_formula(
            formula=formula,
            markets=markets,
            fragrance_concentration=fragrance_concentration,
            is_leave_on=is_leave_on,
        )

    def check_voc(
        self,
        formula: FormulaData,
        product_type: ProductType,
        markets: list[Market],
    ) -> VOCReport:
        """Run VOC-only check.

        Args:
            formula: Formula to check.
            product_type: Product type.
            markets: Target markets.

        Returns:
            VOCReport.
        """
        return self.voc_service.check_formula(
            formula=formula,
            product_type=product_type,
            markets=markets,
        )

    def generate_fse(
        self,
        formula: FormulaData,
        product_type: ProductType,
        fragrance_concentration: float = 100.0,
        intended_use: str = "",
        assessor: Optional[str] = None,
    ) -> FSEReport:
        """Generate Fragrance Safety Evaluation.

        Args:
            formula: Formula to evaluate.
            product_type: Product type.
            fragrance_concentration: Fragrance % in final product.
            intended_use: Description of intended use.
            assessor: Name of assessor.

        Returns:
            FSEReport.
        """
        return self.fse_service.generate_fse(
            formula=formula,
            product_type=product_type,
            fragrance_concentration=fragrance_concentration,
            intended_use=intended_use,
            assessor=assessor,
        )

    def check_formaldehyde(
        self,
        formula: FormulaData,
        markets: list[Market],
        fragrance_concentration: float = 100.0,
    ):
        """Check for formaldehyde donors.

        Args:
            formula: Formula to check.
            markets: Target markets.
            fragrance_concentration: Fragrance % in final product.

        Returns:
            FormaldehydeReport.
        """
        return self.formaldehyde_service.check_formula(
            formula=formula,
            markets=markets,
            fragrance_concentration=fragrance_concentration,
        )

    def _generate_certificate_number(self) -> str:
        """Generate a unique compliance certificate number."""
        timestamp = datetime.now().strftime("%Y%m%d")
        unique_id = uuid4().hex[:8].upper()
        return f"COMP-{timestamp}-{unique_id}"
