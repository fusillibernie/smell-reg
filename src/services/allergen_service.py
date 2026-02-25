"""Allergen detection and disclosure service."""

import json
from pathlib import Path
from typing import Optional

from ..models.regulatory import Market, ProductType
from ..models.allergen import (
    Allergen,
    AllergenResult,
    AllergenReport,
    AllergenRegulation,
)
from ..integrations.aroma_lab import FormulaData


# Default data file location
DEFAULT_ALLERGEN_DATA = Path(__file__).parent.parent.parent / "data" / "regulatory" / "allergens.json"


class AllergenService:
    """Service for allergen detection and disclosure requirements."""

    def __init__(self, data_file: Optional[Path] = None):
        """Initialize the service.

        Args:
            data_file: Path to allergen data JSON file.
        """
        self.data_file = data_file or DEFAULT_ALLERGEN_DATA
        self._allergens: dict[str, Allergen] = {}
        self._loaded = False

    def load(self) -> None:
        """Load allergen data from JSON file."""
        if not self.data_file.exists():
            return

        with open(self.data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data.get("allergens", []):
            allergen = Allergen.from_dict(item)
            self._allergens[allergen.cas_number] = allergen

        self._loaded = True

    def _ensure_loaded(self) -> None:
        """Ensure data is loaded."""
        if not self._loaded:
            self.load()

    def get_allergen(self, cas_number: str) -> Optional[Allergen]:
        """Get allergen by CAS number.

        Args:
            cas_number: CAS registry number.

        Returns:
            Allergen if found, None otherwise.
        """
        self._ensure_loaded()
        return self._allergens.get(cas_number)

    def is_allergen(self, cas_number: str) -> bool:
        """Check if a CAS number is a known allergen.

        Args:
            cas_number: CAS registry number.

        Returns:
            True if substance is a known allergen.
        """
        return self.get_allergen(cas_number) is not None

    def get_applicable_regulations(
        self,
        cas_number: str,
        markets: list[Market],
    ) -> list[str]:
        """Get applicable allergen regulations for a substance in given markets.

        Args:
            cas_number: CAS registry number.
            markets: Target markets.

        Returns:
            List of regulation identifiers.
        """
        allergen = self.get_allergen(cas_number)
        if not allergen:
            return []

        regulations = []
        for market in markets:
            if market in (Market.EU, Market.UK):
                if allergen.eu_26:
                    regulations.append("eu_26")
                if allergen.eu_82:
                    regulations.append("eu_82")
            elif market == Market.CA:
                if allergen.canada_24:
                    regulations.append("canada_24")
                if allergen.canada_81:
                    regulations.append("canada_81")
            elif market == Market.US:
                # US follows IFRA but no mandatory disclosure
                regulations.append("us_ifra")

        return list(set(regulations))

    def check_formula(
        self,
        formula: FormulaData,
        markets: list[Market],
        fragrance_concentration: float,
        is_leave_on: bool = True,
    ) -> AllergenReport:
        """Check formula for allergen content and disclosure requirements.

        Args:
            formula: Formula to check.
            markets: Target markets.
            fragrance_concentration: Fragrance % in final product.
            is_leave_on: True for leave-on products, False for rinse-off.

        Returns:
            AllergenReport with detection and disclosure results.
        """
        self._ensure_loaded()

        detected: list[AllergenResult] = []
        disclosure_required: list[AllergenResult] = []

        for ingredient in formula.ingredients:
            allergen = self.get_allergen(ingredient.cas_number)
            if not allergen:
                continue

            # Calculate concentration in final product
            conc_in_product = ingredient.percentage * (fragrance_concentration / 100.0)

            # Get threshold based on product type
            threshold = allergen.leave_on_threshold if is_leave_on else allergen.rinse_off_threshold

            # Get applicable regulations
            regulations = self.get_applicable_regulations(ingredient.cas_number, markets)

            result = AllergenResult(
                cas_number=ingredient.cas_number,
                name=ingredient.name,
                concentration_in_fragrance=ingredient.percentage,
                concentration_in_product=conc_in_product,
                threshold=threshold,
                requires_disclosure=conc_in_product >= threshold,
                regulations=regulations,
            )

            detected.append(result)
            if result.requires_disclosure:
                disclosure_required.append(result)

        return AllergenReport(
            formula_name=formula.name,
            markets=markets,
            fragrance_concentration=fragrance_concentration,
            is_leave_on=is_leave_on,
            detected_allergens=detected,
            disclosure_required=disclosure_required,
        )

    def get_all_allergens_for_regulation(self, regulation: AllergenRegulation) -> list[Allergen]:
        """Get all allergens for a specific regulation.

        Args:
            regulation: The allergen regulation.

        Returns:
            List of allergens under that regulation.
        """
        self._ensure_loaded()

        result = []
        for allergen in self._allergens.values():
            if regulation == AllergenRegulation.EU_26 and allergen.eu_26:
                result.append(allergen)
            elif regulation == AllergenRegulation.EU_82 and allergen.eu_82:
                result.append(allergen)
            elif regulation == AllergenRegulation.CANADA_24 and allergen.canada_24:
                result.append(allergen)
            elif regulation == AllergenRegulation.CANADA_81 and allergen.canada_81:
                result.append(allergen)

        return result

    def format_disclosure_list(
        self,
        report: AllergenReport,
        market: Market,
    ) -> list[str]:
        """Format allergen disclosure list for labeling.

        Args:
            report: Allergen report.
            market: Target market.

        Returns:
            List of allergen names for disclosure.
        """
        allergens = report.get_disclosure_list_by_market(market)
        # Sort alphabetically and return INCI names where available
        names = []
        for allergen_result in allergens:
            allergen = self.get_allergen(allergen_result.cas_number)
            if allergen and allergen.inci_name:
                names.append(allergen.inci_name)
            else:
                names.append(allergen_result.name)
        return sorted(names)
