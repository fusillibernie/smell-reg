"""IFRA compliance service."""

from dataclasses import dataclass
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
from ..integrations.aroma_lab import (
    AromaLabClient,
    FormulaData,
    IFRACategory,
    IFRARestriction,
    RestrictionType,
)


@dataclass
class IFRAComplianceResult:
    """Detailed IFRA compliance result."""
    is_compliant: bool
    violations: list[ComplianceResult]
    warnings: list[ComplianceResult]
    compliant_ingredients: list[str]
    certificate_number: Optional[str] = None
    amendment_version: str = "51st"


class IFRAService:
    """Service for IFRA compliance checking and certificate generation."""

    def __init__(self, aroma_lab_client: Optional[AromaLabClient] = None):
        """Initialize the service.

        Args:
            aroma_lab_client: Client for aroma-lab data. Creates one if not provided.
        """
        self.client = aroma_lab_client or AromaLabClient()

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
    ) -> IFRAComplianceResult:
        """Check formula for IFRA compliance.

        Args:
            formula: Formula to check.
            product_type: Product type for category determination.
            fragrance_concentration: Fragrance % in final product (for dilution).

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

        violations: list[ComplianceResult] = []
        warnings: list[ComplianceResult] = []
        compliant: list[str] = []

        for ingredient in formula.ingredients:
            restriction = self.client.get_ifra_restriction(ingredient.cas_number)

            if restriction is None:
                # Not restricted
                compliant.append(ingredient.name)
                continue

            # Calculate actual concentration in final product
            actual_conc = ingredient.percentage * (fragrance_concentration / 100.0)
            limit = restriction.get_limit_for_category(category)

            if restriction.restriction_type == RestrictionType.PROHIBITION:
                violations.append(
                    ComplianceResult(
                        requirement=f"IFRA Category {category_str} - Prohibited",
                        status=ComplianceStatus.NON_COMPLIANT,
                        market=Market.US,  # IFRA is global
                        details=f"{ingredient.name} is prohibited under IFRA {restriction.amendment_number or '51st'} Amendment",
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
                            details=f"{ingredient.name} at {actual_conc:.4f}% exceeds limit of {limit}%",
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
                            details=f"{ingredient.name} at {actual_conc:.4f}% is approaching limit of {limit}%",
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
