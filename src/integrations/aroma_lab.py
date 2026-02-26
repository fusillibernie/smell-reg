"""Client for importing data from aroma-lab project.

This module provides data models compatible with aroma-lab and a client
for loading IFRA restriction data from JSON files.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


# Path to aroma-lab project data
AROMA_LAB_PATH = Path("C:/Users/pwong/projects/aroma-lab")


class IFRACategory(Enum):
    """IFRA product categories for restriction levels."""
    CATEGORY_1 = "1"  # Lip products
    CATEGORY_2 = "2"  # Deodorants/antiperspirants
    CATEGORY_3 = "3"  # Eye products, men's facial products
    CATEGORY_4 = "4"  # Fine fragrance
    CATEGORY_5A = "5A"  # Body lotion (hydroalcoholic)
    CATEGORY_5B = "5B"  # Face cream
    CATEGORY_5C = "5C"  # Hand cream
    CATEGORY_5D = "5D"  # Baby products
    CATEGORY_6 = "6"  # Mouthwash, toothpaste
    CATEGORY_7A = "7A"  # Rinse-off hair products
    CATEGORY_7B = "7B"  # Leave-on hair products
    CATEGORY_8 = "8"  # Intimate wipes
    CATEGORY_9 = "9"  # Rinse-off skin products
    CATEGORY_10A = "10A"  # Household cleaners (spray)
    CATEGORY_10B = "10B"  # Household cleaners (other)
    CATEGORY_11A = "11A"  # Candles
    CATEGORY_11B = "11B"  # Reed diffusers
    CATEGORY_12 = "12"  # Air fresheners (non-spray)


class RestrictionType(Enum):
    """Type of IFRA restriction."""
    PROHIBITION = "prohibition"  # Completely banned
    RESTRICTION = "restriction"  # Usage limits apply
    SPECIFICATION = "specification"  # Purity requirements
    SENSITIZATION = "sensitization"  # Allergen limits


@dataclass
class Citation:
    """A literature citation for data provenance."""
    title: str
    authors: list[str] = field(default_factory=list)
    journal: Optional[str] = None
    year: Optional[int] = None
    volume: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    accessed_date: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "authors": self.authors,
            "journal": self.journal,
            "year": self.year,
            "volume": self.volume,
            "pages": self.pages,
            "doi": self.doi,
            "url": self.url,
            "accessed_date": self.accessed_date
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Citation":
        """Create from dictionary."""
        return cls(
            title=data.get("title", ""),
            authors=data.get("authors", []),
            journal=data.get("journal"),
            year=data.get("year"),
            volume=data.get("volume"),
            pages=data.get("pages"),
            doi=data.get("doi"),
            url=data.get("url"),
            accessed_date=data.get("accessed_date")
        )


@dataclass
class IFRARestriction:
    """IFRA restriction data for a single material."""
    cas_number: str
    name: str
    restriction_type: RestrictionType

    # Category-specific limits (percentage)
    category_limits: dict[str, float] = field(default_factory=dict)

    # General limit if same for all categories
    general_limit: Optional[float] = None

    # Amendment information
    amendment_number: Optional[int] = None
    effective_date: Optional[str] = None

    # Additional info
    reason: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "cas_number": self.cas_number,
            "name": self.name,
            "restriction_type": self.restriction_type.value,
            "category_limits": self.category_limits,
            "general_limit": self.general_limit,
            "amendment_number": self.amendment_number,
            "effective_date": self.effective_date,
            "reason": self.reason,
            "notes": self.notes
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IFRARestriction":
        """Create from dictionary."""
        return cls(
            cas_number=data.get("cas_number", ""),
            name=data.get("name", ""),
            restriction_type=RestrictionType(data.get("restriction_type", "restriction")),
            category_limits=data.get("category_limits", {}),
            general_limit=data.get("general_limit"),
            amendment_number=data.get("amendment_number"),
            effective_date=data.get("effective_date"),
            reason=data.get("reason"),
            notes=data.get("notes")
        )

    def get_limit_for_category(self, category: IFRACategory) -> Optional[float]:
        """Get the usage limit for a specific product category."""
        if self.restriction_type == RestrictionType.PROHIBITION:
            return 0.0

        cat_value = category.value
        if cat_value in self.category_limits:
            return self.category_limits[cat_value]
        return self.general_limit


@dataclass
class SafetyData:
    """Safety and regulatory data for a compound."""
    cas_number: str
    name: str

    # IFRA restrictions
    ifra_restriction: Optional[IFRARestriction] = None

    # Allergen information
    is_eu_allergen: bool = False
    allergen_threshold_percent: Optional[float] = None

    # RIFM data
    rifm_id: Optional[str] = None
    rifm_monograph_available: bool = False

    # Toxicity data
    oral_ld50_mg_kg: Optional[float] = None
    dermal_ld50_mg_kg: Optional[float] = None
    skin_sensitization_category: Optional[str] = None

    # Phototoxicity
    is_phototoxic: bool = False
    phototoxicity_limit: Optional[float] = None

    # Environmental
    biodegradable: Optional[bool] = None
    aquatic_toxicity: Optional[str] = None

    # Citations
    citations: list[Citation] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "cas_number": self.cas_number,
            "name": self.name,
            "ifra_restriction": self.ifra_restriction.to_dict() if self.ifra_restriction else None,
            "is_eu_allergen": self.is_eu_allergen,
            "allergen_threshold_percent": self.allergen_threshold_percent,
            "rifm_id": self.rifm_id,
            "rifm_monograph_available": self.rifm_monograph_available,
            "oral_ld50_mg_kg": self.oral_ld50_mg_kg,
            "dermal_ld50_mg_kg": self.dermal_ld50_mg_kg,
            "skin_sensitization_category": self.skin_sensitization_category,
            "is_phototoxic": self.is_phototoxic,
            "phototoxicity_limit": self.phototoxicity_limit,
            "biodegradable": self.biodegradable,
            "aquatic_toxicity": self.aquatic_toxicity,
            "citations": [c.to_dict() for c in self.citations]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SafetyData":
        """Create from dictionary."""
        ifra_data = data.get("ifra_restriction")
        return cls(
            cas_number=data.get("cas_number", ""),
            name=data.get("name", ""),
            ifra_restriction=IFRARestriction.from_dict(ifra_data) if ifra_data else None,
            is_eu_allergen=data.get("is_eu_allergen", False),
            allergen_threshold_percent=data.get("allergen_threshold_percent"),
            rifm_id=data.get("rifm_id"),
            rifm_monograph_available=data.get("rifm_monograph_available", False),
            oral_ld50_mg_kg=data.get("oral_ld50_mg_kg"),
            dermal_ld50_mg_kg=data.get("dermal_ld50_mg_kg"),
            skin_sensitization_category=data.get("skin_sensitization_category"),
            is_phototoxic=data.get("is_phototoxic", False),
            phototoxicity_limit=data.get("phototoxicity_limit"),
            biodegradable=data.get("biodegradable"),
            aquatic_toxicity=data.get("aquatic_toxicity"),
            citations=[Citation.from_dict(c) for c in data.get("citations", [])]
        )

    def is_restricted(self) -> bool:
        """Check if compound has any IFRA restriction."""
        return self.ifra_restriction is not None

    def get_max_usage(self, category: IFRACategory) -> Optional[float]:
        """Get maximum usage percentage for a product category."""
        if not self.ifra_restriction:
            return None
        return self.ifra_restriction.get_limit_for_category(category)


@dataclass
class Aromachemical:
    """Simplified aromachemical model compatible with aroma-lab."""
    cas_number: str
    name: str
    synonyms: list[str] = field(default_factory=list)
    molecular_formula: Optional[str] = None
    molecular_weight: Optional[float] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Aromachemical":
        """Create from dictionary."""
        return cls(
            cas_number=data.get("cas_number", ""),
            name=data.get("name", ""),
            synonyms=data.get("synonyms", []),
            molecular_formula=data.get("molecular_formula"),
            molecular_weight=data.get("molecular_weight")
        )


@dataclass
class FormulaIngredient:
    """An ingredient in a formula."""
    aromachemical: Aromachemical
    percentage: float


@dataclass
class Formula:
    """A fragrance formula."""
    name: str
    ingredients: list[FormulaIngredient] = field(default_factory=list)

    @property
    def total_percentage(self) -> float:
        """Calculate total percentage of all ingredients."""
        return sum(ing.percentage for ing in self.ingredients)


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


class IFRADatabase:
    """Database of IFRA restrictions."""

    def __init__(self, data_path: Optional[Path] = None):
        """Initialize the database.

        Args:
            data_path: Path to IFRA data JSON file.
        """
        self.data_path = data_path or (AROMA_LAB_PATH / "data" / "ifra_restrictions.json")
        self._restrictions: dict[str, IFRARestriction] = {}
        self._loaded = False

    def load(self) -> None:
        """Load IFRA data from JSON file."""
        if self._loaded:
            return

        if self.data_path.exists():
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data.get("restrictions", []):
                    restriction = IFRARestriction.from_dict(item)
                    self._restrictions[restriction.cas_number] = restriction

        self._loaded = True

    def get_by_cas(self, cas_number: str) -> Optional[IFRARestriction]:
        """Get IFRA restriction by CAS number."""
        self.load()
        return self._restrictions.get(cas_number)

    def get_all(self) -> list[IFRARestriction]:
        """Get all IFRA restrictions."""
        self.load()
        return list(self._restrictions.values())

    def check_formula_compliance(
        self,
        formula_dict: dict[str, float],
        category: IFRACategory
    ) -> list[dict]:
        """Check formula for IFRA compliance.

        Args:
            formula_dict: Dictionary of {CAS: percentage}.
            category: IFRA product category.

        Returns:
            List of violations with details.
        """
        self.load()
        violations = []

        for cas, percentage in formula_dict.items():
            restriction = self._restrictions.get(cas)
            if restriction:
                limit = restriction.get_limit_for_category(category)
                if limit is not None and percentage > limit:
                    violations.append({
                        "cas_number": cas,
                        "name": restriction.name,
                        "percentage": percentage,
                        "limit": limit,
                        "restriction_type": restriction.restriction_type.value
                    })

        return violations


# Global database instance
_database: Optional[IFRADatabase] = None


def get_database() -> IFRADatabase:
    """Get the global IFRA database instance."""
    global _database
    if _database is None:
        _database = IFRADatabase()
    return _database


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
        """Convert a Formula to FormulaData.

        Args:
            formula: Formula object.

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
            return IFRACategory(category_str)
        except ValueError:
            # Try with prefix
            try:
                return IFRACategory(f"CATEGORY_{category_str}")
            except ValueError:
                pass
        return None


# Re-export types for convenience
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
    "IFRADatabase",
    "get_database",
]
