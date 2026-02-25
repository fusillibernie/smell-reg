"""Repository for regulatory data access."""

import json
from pathlib import Path
from typing import Optional

from ..models.allergen import Allergen
from ..models.voc import VOCLimit, VOCRegulation


# Default data directory
DEFAULT_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "regulatory"


class RegulatoryDataRepository:
    """Repository for accessing regulatory data."""

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize the repository.

        Args:
            data_dir: Directory containing regulatory data JSON files.
        """
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self._allergens: dict[str, Allergen] = {}
        self._voc_limits: list[VOCLimit] = []
        self._prop65: dict[str, dict] = {}
        self._hotlist: dict[str, dict] = {}
        self._reach: dict[str, dict] = {}
        self._loaded = False

    def load_all(self) -> None:
        """Load all regulatory data files."""
        self._load_allergens()
        self._load_voc_limits()
        self._load_prop65()
        self._load_hotlist()
        self._load_reach()
        self._loaded = True

    def _load_json(self, filename: str) -> dict:
        """Load a JSON file from the data directory."""
        filepath = self.data_dir / filename
        if not filepath.exists():
            return {}
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_allergens(self) -> None:
        """Load allergen data."""
        data = self._load_json("allergens.json")
        for item in data.get("allergens", []):
            allergen = Allergen.from_dict(item)
            self._allergens[allergen.cas_number] = allergen

    def _load_voc_limits(self) -> None:
        """Load VOC limits data."""
        data = self._load_json("voc_limits.json")
        self._voc_limits = [
            VOCLimit.from_dict(item)
            for item in data.get("limits", [])
        ]

    def _load_prop65(self) -> None:
        """Load Prop 65 data."""
        data = self._load_json("prop65.json")
        self._prop65 = {
            item["cas_number"]: item
            for item in data.get("substances", [])
        }

    def _load_hotlist(self) -> None:
        """Load Canada Hotlist data."""
        data = self._load_json("canada_hotlist.json")
        self._hotlist = {
            item["cas_number"]: item
            for item in data.get("substances", [])
        }

    def _load_reach(self) -> None:
        """Load REACH data."""
        data = self._load_json("reach.json")
        self._reach = {
            item["cas_number"]: item
            for item in data.get("substances", [])
        }

    def _ensure_loaded(self) -> None:
        """Ensure data is loaded."""
        if not self._loaded:
            self.load_all()

    # Allergen queries
    def get_allergen(self, cas_number: str) -> Optional[Allergen]:
        """Get allergen by CAS number."""
        self._ensure_loaded()
        return self._allergens.get(cas_number)

    def get_all_allergens(self) -> list[Allergen]:
        """Get all allergens."""
        self._ensure_loaded()
        return list(self._allergens.values())

    def get_eu_26_allergens(self) -> list[Allergen]:
        """Get EU 26 allergens."""
        self._ensure_loaded()
        return [a for a in self._allergens.values() if a.eu_26]

    def get_eu_82_allergens(self) -> list[Allergen]:
        """Get EU 82 allergens."""
        self._ensure_loaded()
        return [a for a in self._allergens.values() if a.eu_82]

    # VOC queries
    def get_voc_limit(
        self,
        regulation: VOCRegulation,
        product_category: str,
    ) -> Optional[float]:
        """Get VOC limit for a regulation and product category."""
        self._ensure_loaded()
        for limit in self._voc_limits:
            if limit.regulation == regulation and limit.product_category == product_category:
                return limit.limit_percent
        return None

    def get_all_voc_limits(self) -> list[VOCLimit]:
        """Get all VOC limits."""
        self._ensure_loaded()
        return self._voc_limits

    # Prop 65 queries
    def get_prop65_substance(self, cas_number: str) -> Optional[dict]:
        """Get Prop 65 substance info."""
        self._ensure_loaded()
        return self._prop65.get(cas_number)

    def is_prop65_listed(self, cas_number: str) -> bool:
        """Check if substance is Prop 65 listed."""
        return self.get_prop65_substance(cas_number) is not None

    # Canada Hotlist queries
    def get_hotlist_substance(self, cas_number: str) -> Optional[dict]:
        """Get Canada Hotlist substance info."""
        self._ensure_loaded()
        return self._hotlist.get(cas_number)

    def is_hotlist_prohibited(self, cas_number: str) -> bool:
        """Check if substance is prohibited on Canada Hotlist."""
        sub = self.get_hotlist_substance(cas_number)
        if sub:
            return sub.get("restriction_type") == "prohibited"
        return False

    # REACH queries
    def get_reach_substance(self, cas_number: str) -> Optional[dict]:
        """Get REACH substance info."""
        self._ensure_loaded()
        return self._reach.get(cas_number)

    def is_svhc(self, cas_number: str) -> bool:
        """Check if substance is an SVHC."""
        sub = self.get_reach_substance(cas_number)
        if sub:
            return sub.get("svhc", False)
        return False


# Singleton repository instance
_repository: Optional[RegulatoryDataRepository] = None


def get_repository() -> RegulatoryDataRepository:
    """Get or create the default repository.

    Returns:
        The singleton repository instance.
    """
    global _repository
    if _repository is None:
        _repository = RegulatoryDataRepository()
    return _repository
