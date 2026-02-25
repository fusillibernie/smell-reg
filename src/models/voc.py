"""VOC (Volatile Organic Compounds) data models."""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional

from .regulatory import ProductType


class VOCRegulation(Enum):
    """VOC regulations by jurisdiction."""
    CARB = "carb"  # California Air Resources Board
    OTC = "otc"  # US OTC (Over-the-Counter) drugs
    CANADA = "canada"  # Canadian CEPA VOC regulations
    EU = "eu"  # EU VOC Directive


@dataclass
class VOCLimit:
    """VOC limit for a product category under a regulation."""
    regulation: VOCRegulation
    product_category: str
    limit_percent: float  # Maximum VOC content as percentage
    effective_date: Optional[date] = None
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "regulation": self.regulation.value,
            "product_category": self.product_category,
            "limit_percent": self.limit_percent,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VOCLimit":
        """Create from dictionary."""
        eff_date = data.get("effective_date")
        return cls(
            regulation=VOCRegulation(data.get("regulation", "carb")),
            product_category=data.get("product_category", ""),
            limit_percent=data.get("limit_percent", 0.0),
            effective_date=date.fromisoformat(eff_date) if eff_date else None,
            notes=data.get("notes"),
        )


@dataclass
class VOCIngredient:
    """VOC content of a single ingredient."""
    cas_number: str
    name: str
    percentage_in_formula: float
    voc_percent: float  # What % of this ingredient is VOC (0-100)
    is_exempt: bool = False  # Exempt compound (e.g., acetone for CARB)
    exempt_reason: Optional[str] = None

    @property
    def voc_contribution(self) -> float:
        """Calculate VOC contribution to total formula."""
        if self.is_exempt:
            return 0.0
        return self.percentage_in_formula * (self.voc_percent / 100.0)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "cas_number": self.cas_number,
            "name": self.name,
            "percentage_in_formula": self.percentage_in_formula,
            "voc_percent": self.voc_percent,
            "is_exempt": self.is_exempt,
            "exempt_reason": self.exempt_reason,
            "voc_contribution": self.voc_contribution,
        }


@dataclass
class VOCCalculation:
    """VOC calculation result for a regulation."""
    regulation: VOCRegulation
    product_category: str
    total_voc_percent: float
    limit_percent: float
    is_compliant: bool
    ingredients: list[VOCIngredient] = field(default_factory=list)
    exempt_voc_percent: float = 0.0  # VOC from exempt compounds

    @property
    def margin(self) -> float:
        """Calculate margin to limit (positive = under limit)."""
        return self.limit_percent - self.total_voc_percent

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "regulation": self.regulation.value,
            "product_category": self.product_category,
            "total_voc_percent": self.total_voc_percent,
            "limit_percent": self.limit_percent,
            "is_compliant": self.is_compliant,
            "margin": self.margin,
            "ingredients": [i.to_dict() for i in self.ingredients],
            "exempt_voc_percent": self.exempt_voc_percent,
        }


@dataclass
class VOCReport:
    """Full VOC compliance report."""
    formula_name: str
    product_type: ProductType
    calculations: list[VOCCalculation] = field(default_factory=list)

    @property
    def is_compliant(self) -> bool:
        """Check if compliant with all applicable regulations."""
        return all(c.is_compliant for c in self.calculations)

    def get_calculation(self, regulation: VOCRegulation) -> Optional[VOCCalculation]:
        """Get calculation for a specific regulation."""
        for calc in self.calculations:
            if calc.regulation == regulation:
                return calc
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "formula_name": self.formula_name,
            "product_type": self.product_type.value,
            "calculations": [c.to_dict() for c in self.calculations],
            "is_compliant": self.is_compliant,
        }


# CARB product categories mapping
CARB_PRODUCT_CATEGORIES = {
    ProductType.AIR_FRESHENER: "Air Fresheners",
    ProductType.HOUSEHOLD_CLEANER: "General Purpose Cleaners",
    ProductType.LAUNDRY_DETERGENT: "Laundry Detergents",
    ProductType.DEODORANT: "Antiperspirants/Deodorants",
    ProductType.SHAMPOO: "Hair Styling Products",  # Approximate
    ProductType.BODY_WASH: "Personal Fragrance Products",
    ProductType.FINE_FRAGRANCE: "Personal Fragrance Products",
}

# CARB VOC limits (as of 2020)
CARB_VOC_LIMITS = {
    "Air Fresheners": 15.0,  # Dual purpose only
    "General Purpose Cleaners": 4.0,
    "Personal Fragrance Products": 75.0,
    "Antiperspirants/Deodorants": 0.0,  # Varies by type
    "Hair Styling Products": 6.0,
    "Laundry Detergents": 0.0,  # No limit for most
}
