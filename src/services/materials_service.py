"""Raw materials database service with search functionality."""

import json
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


# Default data file location
DEFAULT_MATERIALS_DATA = Path(__file__).parent.parent.parent / "data" / "materials" / "raw_materials.json"


@dataclass
class RawMaterial:
    """A raw material in the fragrance database."""
    cas_number: str
    name: str
    inci_name: str
    odor_families: list[str]
    volatility: str
    ifra_restricted: bool
    allergen: bool
    synonyms: list[str]
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "cas_number": self.cas_number,
            "name": self.name,
            "inci_name": self.inci_name,
            "odor_families": self.odor_families,
            "volatility": self.volatility,
            "ifra_restricted": self.ifra_restricted,
            "allergen": self.allergen,
            "synonyms": self.synonyms,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RawMaterial":
        return cls(
            cas_number=data.get("cas_number", ""),
            name=data.get("name", ""),
            inci_name=data.get("inci_name", ""),
            odor_families=data.get("odor_families", []),
            volatility=data.get("volatility", ""),
            ifra_restricted=data.get("ifra_restricted", False),
            allergen=data.get("allergen", False),
            synonyms=data.get("synonyms", []),
            notes=data.get("notes"),
        )


class MaterialsService:
    """Service for searching and managing raw materials."""

    def __init__(self, data_file: Optional[Path] = None):
        """Initialize the service.

        Args:
            data_file: Path to materials data JSON file.
        """
        self.data_file = data_file or DEFAULT_MATERIALS_DATA
        self._materials: dict[str, RawMaterial] = {}
        self._name_index: dict[str, str] = {}  # normalized name -> CAS
        self._loaded = False

    def load(self) -> None:
        """Load materials data from JSON file."""
        if not self.data_file.exists():
            return

        with open(self.data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data.get("materials", []):
            material = RawMaterial.from_dict(item)
            self._materials[material.cas_number] = material

            # Build name index for fuzzy matching
            self._index_name(material.name, material.cas_number)
            self._index_name(material.inci_name, material.cas_number)
            for synonym in material.synonyms:
                self._index_name(synonym, material.cas_number)

        self._loaded = True

    def _normalize_name(self, name: str) -> str:
        """Normalize a name for matching."""
        name = name.lower().strip()
        # Remove common prefixes
        for prefix in ["d-", "l-", "dl-", "(+)-", "(-)-", "(±)-", "(r)-", "(s)-",
                       "alpha-", "α-", "beta-", "β-", "gamma-", "γ-", "cis-", "trans-"]:
            if name.startswith(prefix):
                name = name[len(prefix):]
        # Remove parenthetical annotations
        name = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
        # Remove special characters
        name = re.sub(r'[^\w\s]', '', name)
        return name.strip()

    def _index_name(self, name: str, cas_number: str) -> None:
        """Add a name to the search index."""
        if not name:
            return
        normalized = self._normalize_name(name)
        if normalized:
            self._name_index[normalized] = cas_number

    def _ensure_loaded(self) -> None:
        """Ensure data is loaded."""
        if not self._loaded:
            self.load()

    def get_by_cas(self, cas_number: str) -> Optional[RawMaterial]:
        """Get material by CAS number.

        Args:
            cas_number: CAS registry number.

        Returns:
            RawMaterial if found, None otherwise.
        """
        self._ensure_loaded()
        return self._materials.get(cas_number)

    def get_by_name(self, name: str) -> Optional[RawMaterial]:
        """Get material by name (fuzzy matching).

        Args:
            name: Material name to search.

        Returns:
            RawMaterial if found, None otherwise.
        """
        self._ensure_loaded()
        normalized = self._normalize_name(name)
        cas_number = self._name_index.get(normalized)
        if cas_number:
            return self._materials.get(cas_number)
        return None

    def search(self, query: str, limit: int = 20) -> list[RawMaterial]:
        """Search materials by name, CAS, or INCI name.

        Args:
            query: Search query.
            limit: Maximum results to return.

        Returns:
            List of matching materials.
        """
        self._ensure_loaded()
        query_lower = query.lower().strip()
        query_normalized = self._normalize_name(query)

        results = []
        seen_cas = set()

        # Exact CAS match first
        if query in self._materials:
            material = self._materials[query]
            results.append(material)
            seen_cas.add(material.cas_number)

        # Exact name match
        if query_normalized in self._name_index:
            cas = self._name_index[query_normalized]
            if cas not in seen_cas:
                results.append(self._materials[cas])
                seen_cas.add(cas)

        # Prefix/contains matching
        for material in self._materials.values():
            if material.cas_number in seen_cas:
                continue

            # Check all searchable fields
            searchable = [
                material.name.lower(),
                material.inci_name.lower(),
                material.cas_number,
            ] + [s.lower() for s in material.synonyms]

            for field in searchable:
                if query_lower in field or field.startswith(query_lower):
                    results.append(material)
                    seen_cas.add(material.cas_number)
                    break

            if len(results) >= limit:
                break

        return results[:limit]

    def search_by_odor_family(self, odor_family: str) -> list[RawMaterial]:
        """Search materials by odor family.

        Args:
            odor_family: Odor family to search (e.g., "floral", "woody").

        Returns:
            List of matching materials.
        """
        self._ensure_loaded()
        odor_lower = odor_family.lower()
        return [
            m for m in self._materials.values()
            if odor_lower in [f.lower() for f in m.odor_families]
        ]

    def get_allergens(self) -> list[RawMaterial]:
        """Get all materials flagged as allergens.

        Returns:
            List of allergen materials.
        """
        self._ensure_loaded()
        return [m for m in self._materials.values() if m.allergen]

    def get_all(self) -> list[RawMaterial]:
        """Get all materials.

        Returns:
            List of all materials.
        """
        self._ensure_loaded()
        return list(self._materials.values())

    def get_count(self) -> int:
        """Get total number of materials.

        Returns:
            Material count.
        """
        self._ensure_loaded()
        return len(self._materials)
