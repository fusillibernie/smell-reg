"""Client for importing data from aroma-lab project."""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Add aroma-lab to path for imports
AROMA_LAB_PATH = Path("C:/Users/pwong/projects/aroma-lab")
if str(AROMA_LAB_PATH) not in sys.path:
    sys.path.insert(0, str(AROMA_LAB_PATH))

# Import aroma-lab models
from src.models import Aromachemical, Formula, FormulaIngredient
from src.literature.data_models import (
    IFRACategory,
    RestrictionType,
    IFRARestriction,
    SafetyData,
    Citation,
)
from src.literature.ifra_data import IFRADatabase, get_database


@dataclass
class FormulaIngredientData:
    """Simplified ingredient data for compliance checking."""
    cas_number: str
    name: str
    percentage: float


@dataclass
class FormulaData:
    """Simplified formula data for compliance checking."""
    name: str
    ingredients: list[FormulaIngredientData]
    total_percentage: float = 100.0

    def to_cas_percentage_dict(self) -> dict[str, float]:
        """Convert to {CAS: percentage} format for IFRA checking."""
        return {ing.cas_number: ing.percentage for ing in self.ingredients}


class AromaLabClient:
    """Client for interacting with aroma-lab data."""

    def __init__(self, aroma_lab_path: Optional[Path] = None):
        """Initialize the client.

        Args:
            aroma_lab_path: Path to aroma-lab project. Defaults to standard location.
        """
        self.aroma_lab_path = aroma_lab_path or AROMA_LAB_PATH
        self._ifra_db: Optional[IFRADatabase] = None

    @property
    def ifra_database(self) -> IFRADatabase:
        """Get the IFRA database instance."""
        if self._ifra_db is None:
            self._ifra_db = get_database()
        return self._ifra_db

    def convert_formula(self, formula: Formula) -> FormulaData:
        """Convert an aroma-lab Formula to FormulaData.

        Args:
            formula: aroma-lab Formula object.

        Returns:
            FormulaData for compliance checking.
        """
        ingredients = [
            FormulaIngredientData(
                cas_number=ing.aromachemical.cas_number,
                name=ing.aromachemical.name,
                percentage=ing.percentage,
            )
            for ing in formula.ingredients
        ]
        return FormulaData(
            name=formula.name,
            ingredients=ingredients,
            total_percentage=formula.total_percentage,
        )

    def get_ifra_restriction(self, cas_number: str) -> Optional[IFRARestriction]:
        """Get IFRA restriction for a CAS number.

        Args:
            cas_number: CAS registry number.

        Returns:
            IFRARestriction if restricted, None otherwise.
        """
        return self.ifra_database.get_by_cas(cas_number)

    def check_ifra_compliance(
        self,
        formula_data: FormulaData,
        category: IFRACategory,
    ) -> list[dict]:
        """Check formula for IFRA compliance.

        Args:
            formula_data: Formula data to check.
            category: IFRA product category.

        Returns:
            List of violations.
        """
        formula_dict = formula_data.to_cas_percentage_dict()
        return self.ifra_database.check_formula_compliance(formula_dict, category)

    def get_ifra_category(self, category_str: str) -> Optional[IFRACategory]:
        """Get IFRACategory from string.

        Args:
            category_str: Category string like "4" or "5A".

        Returns:
            IFRACategory enum value.
        """
        try:
            return IFRACategory(f"CATEGORY_{category_str}")
        except ValueError:
            # Try direct lookup
            for cat in IFRACategory:
                if cat.value == category_str:
                    return cat
        return None


# Re-export aroma-lab types for convenience
__all__ = [
    "AromaLabClient",
    "FormulaData",
    "FormulaIngredientData",
    "IFRACategory",
    "RestrictionType",
    "IFRARestriction",
    "SafetyData",
    "Citation",
    "Aromachemical",
    "Formula",
    "FormulaIngredient",
]
