"""Natural materials service for IFRA incidentals tracking.

This service provides access to natural material composition data
from IFRA Annex IV (Transparency List) to properly calculate
restricted substance totals including incidentals.
"""

import json
from pathlib import Path
from typing import Optional

from ..models.naturals import NaturalMaterial, RestrictedConstituent, IncidentalReport
from ..integrations.aroma_lab import FormulaData


# Default data file location
DEFAULT_NATURALS_DATA = Path(__file__).parent.parent.parent / "data" / "regulatory" / "naturals.json"


class NaturalsService:
    """Service for natural material composition and incidentals calculation."""

    def __init__(self, data_file: Optional[Path] = None):
        """Initialize the service.

        Args:
            data_file: Path to naturals data JSON file.
        """
        self.data_file = data_file or DEFAULT_NATURALS_DATA
        self._naturals: dict[str, NaturalMaterial] = {}
        self._loaded = False

    def load(self) -> None:
        """Load natural materials data from JSON file."""
        if not self.data_file.exists():
            return

        with open(self.data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data.get("naturals", []):
            natural = NaturalMaterial.from_dict(item)
            self._naturals[natural.cas_number] = natural

        self._loaded = True

    def _ensure_loaded(self) -> None:
        """Ensure data is loaded."""
        if not self._loaded:
            self.load()

    def get_natural(self, cas_number: str) -> Optional[NaturalMaterial]:
        """Get natural material by CAS number.

        Args:
            cas_number: CAS registry number of the natural material.

        Returns:
            NaturalMaterial if found, None otherwise.
        """
        self._ensure_loaded()
        return self._naturals.get(cas_number)

    def is_natural(self, cas_number: str) -> bool:
        """Check if a CAS number is a known natural material.

        Args:
            cas_number: CAS registry number.

        Returns:
            True if CAS is a natural material with composition data.
        """
        return self.get_natural(cas_number) is not None

    def get_all_naturals(self) -> list[NaturalMaterial]:
        """Get all natural materials.

        Returns:
            List of all natural materials.
        """
        self._ensure_loaded()
        return list(self._naturals.values())

    def calculate_incidentals(
        self,
        formula: FormulaData,
    ) -> tuple[dict[str, float], list[IncidentalReport]]:
        """Calculate all incidentals from natural materials in a formula.

        This calculates the total contribution of each restricted substance
        from the natural materials in the formula.

        Args:
            formula: Formula to analyze.

        Returns:
            Tuple of:
            - Dictionary mapping CAS number to total incidental percentage
            - List of IncidentalReports for each natural material used
        """
        self._ensure_loaded()

        incidental_totals: dict[str, float] = {}
        reports: list[IncidentalReport] = []

        for ingredient in formula.ingredients:
            natural = self.get_natural(ingredient.cas_number)
            if not natural:
                continue

            # This ingredient is a natural material
            report_incidentals = []

            # Calculate contribution from each restricted constituent
            for constituent in natural.restricted_constituents:
                contribution = natural.get_restricted_constituent_total(
                    constituent.cas_number,
                    ingredient.percentage
                )
                if contribution > 0:
                    if constituent.cas_number in incidental_totals:
                        incidental_totals[constituent.cas_number] += contribution
                    else:
                        incidental_totals[constituent.cas_number] = contribution

                    report_incidentals.append({
                        "cas_number": constituent.cas_number,
                        "name": constituent.name,
                        "contributed_percentage": contribution,
                    })

            # Also track allergen constituents
            for constituent in natural.allergen_constituents:
                # Avoid double-counting if already in restricted
                if any(c.cas_number == constituent.cas_number for c in natural.restricted_constituents):
                    continue

                contribution = natural.get_restricted_constituent_total(
                    constituent.cas_number,
                    ingredient.percentage
                )
                if contribution > 0:
                    if constituent.cas_number in incidental_totals:
                        incidental_totals[constituent.cas_number] += contribution
                    else:
                        incidental_totals[constituent.cas_number] = contribution

                    report_incidentals.append({
                        "cas_number": constituent.cas_number,
                        "name": constituent.name,
                        "contributed_percentage": contribution,
                    })

            if report_incidentals:
                reports.append(IncidentalReport(
                    natural_name=natural.name,
                    natural_cas=natural.cas_number,
                    natural_percentage=ingredient.percentage,
                    incidentals=report_incidentals,
                ))

        return incidental_totals, reports

    def get_restricted_constituent_sources(
        self,
        cas_number: str,
    ) -> list[tuple[NaturalMaterial, float]]:
        """Find all natural materials containing a specific restricted substance.

        Args:
            cas_number: CAS of the restricted substance.

        Returns:
            List of (NaturalMaterial, max_percentage) tuples.
        """
        self._ensure_loaded()

        sources = []
        for natural in self._naturals.values():
            constituent = natural.get_constituent(cas_number)
            if constituent:
                sources.append((natural, constituent.max_percentage))

        return sources
