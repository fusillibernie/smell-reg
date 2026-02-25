"""Core regulatory data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Market(Enum):
    """Target market regions for regulatory compliance."""
    US = "us"
    EU = "eu"
    CA = "ca"  # Canada
    UK = "uk"
    JP = "jp"  # Japan
    CN = "cn"  # China
    AU = "au"  # Australia
    BR = "br"  # Brazil


class ProductType(Enum):
    """Consumer product types with different regulatory requirements."""
    FINE_FRAGRANCE = "fine_fragrance"
    BODY_LOTION = "body_lotion"
    FACE_CREAM = "face_cream"
    HAND_CREAM = "hand_cream"
    DEODORANT = "deodorant"
    SHAMPOO = "shampoo"
    CONDITIONER = "conditioner"
    BODY_WASH = "body_wash"
    SOAP = "soap"
    CANDLE = "candle"
    REED_DIFFUSER = "reed_diffuser"
    AIR_FRESHENER = "air_freshener"
    HOUSEHOLD_CLEANER = "household_cleaner"
    LAUNDRY_DETERGENT = "laundry_detergent"
    LIP_PRODUCT = "lip_product"
    BABY_PRODUCT = "baby_product"


class ComplianceStatus(Enum):
    """Status of compliance check result."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    WARNING = "warning"  # Approaching limits
    NOT_APPLICABLE = "not_applicable"


@dataclass
class ComplianceResult:
    """Result of a single compliance check."""
    requirement: str  # e.g., "IFRA Category 4", "EU Allergen Disclosure"
    status: ComplianceStatus
    market: Market
    details: str = ""
    cas_number: Optional[str] = None
    ingredient_name: Optional[str] = None
    current_value: Optional[float] = None  # Current percentage/value
    limit_value: Optional[float] = None  # Regulatory limit
    regulation_reference: Optional[str] = None  # e.g., "EC 1223/2009"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "requirement": self.requirement,
            "status": self.status.value,
            "market": self.market.value,
            "details": self.details,
            "cas_number": self.cas_number,
            "ingredient_name": self.ingredient_name,
            "current_value": self.current_value,
            "limit_value": self.limit_value,
            "regulation_reference": self.regulation_reference,
        }


@dataclass
class ComplianceReport:
    """Full compliance report for a formula."""
    formula_name: str
    product_type: ProductType
    markets: list[Market]
    fragrance_concentration: float  # Fragrance % in final product
    results: list[ComplianceResult] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)
    certificate_number: Optional[str] = None

    @property
    def is_compliant(self) -> bool:
        """Check if all results are compliant."""
        return all(
            r.status in (ComplianceStatus.COMPLIANT, ComplianceStatus.NOT_APPLICABLE)
            for r in self.results
        )

    @property
    def non_compliant_items(self) -> list[ComplianceResult]:
        """Get list of non-compliant results."""
        return [r for r in self.results if r.status == ComplianceStatus.NON_COMPLIANT]

    @property
    def warnings(self) -> list[ComplianceResult]:
        """Get list of warning results."""
        return [r for r in self.results if r.status == ComplianceStatus.WARNING]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "formula_name": self.formula_name,
            "product_type": self.product_type.value,
            "markets": [m.value for m in self.markets],
            "fragrance_concentration": self.fragrance_concentration,
            "results": [r.to_dict() for r in self.results],
            "generated_at": self.generated_at.isoformat(),
            "certificate_number": self.certificate_number,
            "is_compliant": self.is_compliant,
        }


# Mapping from ProductType to IFRA Category
PRODUCT_TO_IFRA_CATEGORY = {
    ProductType.LIP_PRODUCT: "1",
    ProductType.DEODORANT: "2",
    ProductType.FINE_FRAGRANCE: "4",
    ProductType.BODY_LOTION: "5A",
    ProductType.FACE_CREAM: "5B",
    ProductType.HAND_CREAM: "5C",
    ProductType.BABY_PRODUCT: "5D",
    ProductType.SHAMPOO: "7A",
    ProductType.CONDITIONER: "7A",
    ProductType.BODY_WASH: "9",
    ProductType.SOAP: "9",
    ProductType.HOUSEHOLD_CLEANER: "10B",
    ProductType.LAUNDRY_DETERGENT: "10B",
    ProductType.CANDLE: "11A",
    ProductType.REED_DIFFUSER: "11B",
    ProductType.AIR_FRESHENER: "12",
}
