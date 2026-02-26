"""Natural material models for IFRA incidentals tracking.

IFRA publishes data on restricted substance content in natural materials
(Annex IV - Transparency List). This module provides models to track
these incidentals for proper compliance calculation.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RestrictedConstituent:
    """A restricted substance found in a natural material."""
    cas_number: str
    name: str
    max_percentage: float  # Maximum % found in the natural
    typical_percentage: Optional[float] = None  # Typical/average %
    notes: Optional[str] = None


@dataclass
class NaturalMaterial:
    """A natural material (essential oil, absolute, etc.) with its constituents.

    Based on IFRA Annex IV / Transparency List data.
    """
    cas_number: str  # CAS of the natural material itself
    name: str
    botanical_name: Optional[str] = None
    material_type: str = "essential_oil"  # essential_oil, absolute, resinoid, etc.

    # IFRA-restricted constituents found in this natural
    restricted_constituents: list[RestrictedConstituent] = field(default_factory=list)

    # Other allergens present (for EU/CA allergen declarations)
    allergen_constituents: list[RestrictedConstituent] = field(default_factory=list)

    # Reference information
    ifra_annex_reference: Optional[str] = None
    notes: Optional[str] = None

    def get_constituent(self, cas_number: str) -> Optional[RestrictedConstituent]:
        """Get a specific constituent by CAS number."""
        for c in self.restricted_constituents:
            if c.cas_number == cas_number:
                return c
        for c in self.allergen_constituents:
            if c.cas_number == cas_number:
                return c
        return None

    def get_restricted_constituent_total(self, cas_number: str, natural_percentage: float) -> float:
        """Calculate the amount of a restricted substance from this natural.

        Args:
            cas_number: CAS of the restricted substance.
            natural_percentage: Percentage of this natural in the formula.

        Returns:
            Calculated percentage of the restricted substance from this natural.
        """
        constituent = self.get_constituent(cas_number)
        if not constituent:
            return 0.0

        # Use max percentage for conservative compliance calculation
        return (constituent.max_percentage / 100.0) * natural_percentage

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "cas_number": self.cas_number,
            "name": self.name,
            "botanical_name": self.botanical_name,
            "material_type": self.material_type,
            "restricted_constituents": [
                {
                    "cas_number": c.cas_number,
                    "name": c.name,
                    "max_percentage": c.max_percentage,
                    "typical_percentage": c.typical_percentage,
                    "notes": c.notes,
                }
                for c in self.restricted_constituents
            ],
            "allergen_constituents": [
                {
                    "cas_number": c.cas_number,
                    "name": c.name,
                    "max_percentage": c.max_percentage,
                    "typical_percentage": c.typical_percentage,
                    "notes": c.notes,
                }
                for c in self.allergen_constituents
            ],
            "ifra_annex_reference": self.ifra_annex_reference,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NaturalMaterial":
        """Create from dictionary."""
        return cls(
            cas_number=data.get("cas_number", ""),
            name=data.get("name", ""),
            botanical_name=data.get("botanical_name"),
            material_type=data.get("material_type", "essential_oil"),
            restricted_constituents=[
                RestrictedConstituent(
                    cas_number=c.get("cas_number", ""),
                    name=c.get("name", ""),
                    max_percentage=c.get("max_percentage", 0.0),
                    typical_percentage=c.get("typical_percentage"),
                    notes=c.get("notes"),
                )
                for c in data.get("restricted_constituents", [])
            ],
            allergen_constituents=[
                RestrictedConstituent(
                    cas_number=c.get("cas_number", ""),
                    name=c.get("name", ""),
                    max_percentage=c.get("max_percentage", 0.0),
                    typical_percentage=c.get("typical_percentage"),
                    notes=c.get("notes"),
                )
                for c in data.get("allergen_constituents", [])
            ],
            ifra_annex_reference=data.get("ifra_annex_reference"),
            notes=data.get("notes"),
        )


@dataclass
class IncidentalReport:
    """Report of incidentals from natural materials in a formula."""
    natural_name: str
    natural_cas: str
    natural_percentage: float
    incidentals: list[dict] = field(default_factory=list)
    # Each incidental: {"cas_number", "name", "contributed_percentage"}
