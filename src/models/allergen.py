"""Allergen data models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .regulatory import Market


class AllergenRegulation(Enum):
    """Allergen disclosure regulations."""
    EU_26 = "eu_26"  # Original 26 EU allergens (EC 1223/2009)
    EU_82 = "eu_82"  # Expanded 82 EU allergens (EC 2023/1545)
    CANADA_24 = "ca_24"  # Health Canada 24 allergens
    CANADA_81 = "ca_81"  # Health Canada expanded list
    US_IFRA = "us_ifra"  # US follows IFRA guidelines


@dataclass
class Allergen:
    """Allergen substance data."""
    cas_number: str
    name: str
    inci_name: Optional[str] = None

    # Regulation membership
    eu_26: bool = False
    eu_82: bool = False
    canada_24: bool = False
    canada_81: bool = False

    # Disclosure thresholds (in percentage)
    leave_on_threshold: float = 0.001  # 0.001% = 10 ppm
    rinse_off_threshold: float = 0.01  # 0.01% = 100 ppm

    # Additional info
    synonyms: list[str] = field(default_factory=list)
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "cas_number": self.cas_number,
            "name": self.name,
            "inci_name": self.inci_name,
            "eu_26": self.eu_26,
            "eu_82": self.eu_82,
            "canada_24": self.canada_24,
            "canada_81": self.canada_81,
            "leave_on_threshold": self.leave_on_threshold,
            "rinse_off_threshold": self.rinse_off_threshold,
            "synonyms": self.synonyms,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Allergen":
        """Create from dictionary."""
        return cls(
            cas_number=data.get("cas_number", ""),
            name=data.get("name", ""),
            inci_name=data.get("inci_name"),
            eu_26=data.get("eu_26", False),
            eu_82=data.get("eu_82", False),
            canada_24=data.get("canada_24", False),
            canada_81=data.get("canada_81", False),
            leave_on_threshold=data.get("leave_on_threshold", 0.001),
            rinse_off_threshold=data.get("rinse_off_threshold", 0.01),
            synonyms=data.get("synonyms", []),
            notes=data.get("notes"),
        )


@dataclass
class AllergenResult:
    """Result of allergen detection for a single ingredient."""
    cas_number: str
    name: str
    concentration_in_fragrance: float  # % in fragrance
    concentration_in_product: float  # % in final product
    threshold: float  # Disclosure threshold
    requires_disclosure: bool
    regulations: list[str] = field(default_factory=list)  # Which regulations apply

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "cas_number": self.cas_number,
            "name": self.name,
            "concentration_in_fragrance": self.concentration_in_fragrance,
            "concentration_in_product": self.concentration_in_product,
            "threshold": self.threshold,
            "requires_disclosure": self.requires_disclosure,
            "regulations": self.regulations,
        }


@dataclass
class AllergenReport:
    """Full allergen report for a formula."""
    formula_name: str
    markets: list[Market]
    fragrance_concentration: float
    is_leave_on: bool  # Leave-on vs rinse-off product
    detected_allergens: list[AllergenResult] = field(default_factory=list)
    disclosure_required: list[AllergenResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "formula_name": self.formula_name,
            "markets": [m.value for m in self.markets],
            "fragrance_concentration": self.fragrance_concentration,
            "is_leave_on": self.is_leave_on,
            "detected_allergens": [a.to_dict() for a in self.detected_allergens],
            "disclosure_required": [a.to_dict() for a in self.disclosure_required],
        }

    def get_disclosure_list_by_market(self, market: Market) -> list[AllergenResult]:
        """Get allergens requiring disclosure for a specific market."""
        market_regulations = {
            Market.EU: ["eu_26", "eu_82"],
            Market.UK: ["eu_26", "eu_82"],
            Market.CA: ["canada_24", "canada_81"],
            Market.US: ["us_ifra"],
        }
        regs = market_regulations.get(market, [])
        return [
            a for a in self.disclosure_required
            if any(r in a.regulations for r in regs)
        ]
