"""VOC (Volatile Organic Compounds) compliance service."""

import json
from pathlib import Path
from typing import Optional

from ..models.regulatory import Market, ProductType
from ..models.voc import (
    VOCRegulation,
    VOCLimit,
    VOCIngredient,
    VOCCalculation,
    VOCReport,
    CARB_PRODUCT_CATEGORIES,
    CARB_VOC_LIMITS,
)
from ..integrations.aroma_lab import FormulaData


# Default data file locations
DEFAULT_VOC_LIMITS_FILE = Path(__file__).parent.parent.parent / "data" / "regulatory" / "voc_limits.json"
DEFAULT_VOC_INGREDIENTS_FILE = Path(__file__).parent.parent.parent / "data" / "regulatory" / "voc_ingredients.json"


class VOCService:
    """Service for VOC compliance calculations."""

    def __init__(
        self,
        limits_file: Optional[Path] = None,
        ingredients_file: Optional[Path] = None,
    ):
        """Initialize the service.

        Args:
            limits_file: Path to VOC limits JSON file.
            ingredients_file: Path to VOC ingredient data JSON file.
        """
        self.limits_file = limits_file or DEFAULT_VOC_LIMITS_FILE
        self.ingredients_file = ingredients_file or DEFAULT_VOC_INGREDIENTS_FILE
        self._limits: list[VOCLimit] = []
        self._ingredient_voc: dict[str, dict] = {}  # CAS -> VOC data
        self._exempt_cas: set[str] = set()  # CAS numbers of exempt compounds
        self._loaded = False

    def load(self) -> None:
        """Load VOC data from JSON files."""
        # Load limits
        if self.limits_file.exists():
            with open(self.limits_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._limits = [VOCLimit.from_dict(item) for item in data.get("limits", [])]

        # Load ingredient VOC data
        if self.ingredients_file.exists():
            with open(self.ingredients_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._ingredient_voc = {item["cas_number"]: item for item in data.get("ingredients", [])}
            self._exempt_cas = {
                cas for cas, info in self._ingredient_voc.items()
                if info.get("is_exempt", False)
            }

        self._loaded = True

    def _ensure_loaded(self) -> None:
        """Ensure data is loaded."""
        if not self._loaded:
            self.load()

    def get_limit(
        self,
        regulation: VOCRegulation,
        product_category: str,
    ) -> Optional[float]:
        """Get VOC limit for a regulation and product category.

        Args:
            regulation: VOC regulation.
            product_category: Product category name.

        Returns:
            VOC limit percentage, or None if not found.
        """
        self._ensure_loaded()

        for limit in self._limits:
            if limit.regulation == regulation and limit.product_category == product_category:
                return limit.limit_percent

        # Fallback to CARB hardcoded limits
        if regulation == VOCRegulation.CARB:
            return CARB_VOC_LIMITS.get(product_category)

        return None

    def get_ingredient_voc_percent(self, cas_number: str) -> float:
        """Get VOC percentage for an ingredient.

        Args:
            cas_number: CAS registry number.

        Returns:
            VOC percentage (0-100). Defaults to 100 if unknown.
        """
        self._ensure_loaded()

        if cas_number in self._ingredient_voc:
            return self._ingredient_voc[cas_number].get("voc_percent", 100.0)

        # Default: assume 100% VOC for unknown fragrance ingredients
        return 100.0

    def is_exempt(self, cas_number: str, regulation: VOCRegulation) -> tuple[bool, Optional[str]]:
        """Check if an ingredient is exempt from VOC calculations.

        Args:
            cas_number: CAS registry number.
            regulation: VOC regulation.

        Returns:
            Tuple of (is_exempt, reason).
        """
        self._ensure_loaded()

        if cas_number in self._ingredient_voc:
            info = self._ingredient_voc[cas_number]
            if info.get("is_exempt", False):
                return True, info.get("exempt_reason", "Exempt compound")

        return False, None

    def calculate_voc(
        self,
        formula: FormulaData,
        product_type: ProductType,
        regulation: VOCRegulation,
    ) -> VOCCalculation:
        """Calculate VOC content for a formula under a regulation.

        Args:
            formula: Formula to analyze.
            product_type: Product type.
            regulation: VOC regulation.

        Returns:
            VOCCalculation with results.
        """
        self._ensure_loaded()

        # Get product category for regulation
        product_category = self._get_product_category(product_type, regulation)
        limit = self.get_limit(regulation, product_category)

        if limit is None:
            limit = 100.0  # No limit

        ingredients: list[VOCIngredient] = []
        total_voc = 0.0
        exempt_voc = 0.0

        for ing in formula.ingredients:
            voc_percent = self.get_ingredient_voc_percent(ing.cas_number)
            is_exempt, exempt_reason = self.is_exempt(ing.cas_number, regulation)

            voc_ing = VOCIngredient(
                cas_number=ing.cas_number,
                name=ing.name,
                percentage_in_formula=ing.percentage,
                voc_percent=voc_percent,
                is_exempt=is_exempt,
                exempt_reason=exempt_reason,
            )
            ingredients.append(voc_ing)

            if is_exempt:
                exempt_voc += voc_ing.voc_contribution
            else:
                total_voc += voc_ing.voc_contribution

        return VOCCalculation(
            regulation=regulation,
            product_category=product_category,
            total_voc_percent=total_voc,
            limit_percent=limit,
            is_compliant=total_voc <= limit,
            ingredients=ingredients,
            exempt_voc_percent=exempt_voc,
        )

    def check_formula(
        self,
        formula: FormulaData,
        product_type: ProductType,
        markets: list[Market],
    ) -> VOCReport:
        """Check formula for VOC compliance across markets.

        Args:
            formula: Formula to check.
            product_type: Product type.
            markets: Target markets.

        Returns:
            VOCReport with calculations for all applicable regulations.
        """
        calculations: list[VOCCalculation] = []

        for market in markets:
            regulations = self._get_regulations_for_market(market)
            for reg in regulations:
                calc = self.calculate_voc(formula, product_type, reg)
                calculations.append(calc)

        return VOCReport(
            formula_name=formula.name,
            product_type=product_type,
            calculations=calculations,
        )

    def _get_product_category(
        self,
        product_type: ProductType,
        regulation: VOCRegulation,
    ) -> str:
        """Get product category name for a regulation."""
        if regulation == VOCRegulation.CARB:
            return CARB_PRODUCT_CATEGORIES.get(product_type, "Personal Fragrance Products")
        elif regulation == VOCRegulation.CANADA:
            # Canada uses similar categories
            return CARB_PRODUCT_CATEGORIES.get(product_type, "Personal Fragrance Products")
        return "General"

    def _get_regulations_for_market(self, market: Market) -> list[VOCRegulation]:
        """Get applicable VOC regulations for a market."""
        if market == Market.US:
            return [VOCRegulation.CARB]  # California
        elif market == Market.CA:
            return [VOCRegulation.CANADA]
        elif market == Market.EU:
            return [VOCRegulation.EU]
        return []
