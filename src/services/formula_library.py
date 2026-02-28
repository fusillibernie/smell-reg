"""Formula library service for storing and managing formulas."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


# Default storage location
DEFAULT_LIBRARY_PATH = Path(__file__).parent.parent.parent / "data" / "formulas"


@dataclass
class StoredFormula:
    """A stored formula in the library."""
    id: str
    name: str
    ingredients: list[dict]
    created_at: str
    updated_at: str
    description: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    compliance_status: Optional[str] = None
    last_checked: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "ingredients": self.ingredients,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "description": self.description,
            "tags": self.tags,
            "compliance_status": self.compliance_status,
            "last_checked": self.last_checked,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StoredFormula":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            ingredients=data.get("ingredients", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            description=data.get("description"),
            tags=data.get("tags", []),
            compliance_status=data.get("compliance_status"),
            last_checked=data.get("last_checked"),
        )


class FormulaLibrary:
    """Service for storing and managing formulas."""

    def __init__(self, library_path: Optional[Path] = None):
        """Initialize the library.

        Args:
            library_path: Directory to store formula files.
        """
        self.library_path = library_path or DEFAULT_LIBRARY_PATH
        self._formulas: dict[str, StoredFormula] = {}
        self._loaded = False

    def _ensure_directory(self) -> None:
        """Ensure the library directory exists."""
        self.library_path.mkdir(parents=True, exist_ok=True)

    def _get_index_path(self) -> Path:
        """Get path to the formula index file."""
        return self.library_path / "index.json"

    def load(self) -> None:
        """Load all formulas from the library."""
        self._ensure_directory()
        index_path = self._get_index_path()

        if index_path.exists():
            with open(index_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for item in data.get("formulas", []):
                formula = StoredFormula.from_dict(item)
                self._formulas[formula.id] = formula

        self._loaded = True

    def _save_index(self) -> None:
        """Save the formula index to disk."""
        self._ensure_directory()
        index_path = self._get_index_path()

        data = {
            "metadata": {
                "description": "Formula library index",
                "last_updated": datetime.now().isoformat(),
            },
            "formulas": [f.to_dict() for f in self._formulas.values()],
        }

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _ensure_loaded(self) -> None:
        """Ensure formulas are loaded."""
        if not self._loaded:
            self.load()

    def save(
        self,
        name: str,
        ingredients: list[dict],
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        formula_id: Optional[str] = None,
    ) -> StoredFormula:
        """Save a formula to the library.

        Args:
            name: Formula name.
            ingredients: List of ingredient dicts with cas_number, name, percentage.
            description: Optional description.
            tags: Optional tags for categorization.
            formula_id: Optional ID for updating existing formula.

        Returns:
            The saved formula.
        """
        self._ensure_loaded()

        now = datetime.now().isoformat()

        if formula_id and formula_id in self._formulas:
            # Update existing formula
            formula = self._formulas[formula_id]
            formula.name = name
            formula.ingredients = ingredients
            formula.updated_at = now
            formula.description = description
            formula.tags = tags or []
        else:
            # Create new formula
            formula = StoredFormula(
                id=str(uuid.uuid4()),
                name=name,
                ingredients=ingredients,
                created_at=now,
                updated_at=now,
                description=description,
                tags=tags or [],
            )
            self._formulas[formula.id] = formula

        self._save_index()
        return formula

    def get(self, formula_id: str) -> Optional[StoredFormula]:
        """Get a formula by ID.

        Args:
            formula_id: Formula ID.

        Returns:
            StoredFormula if found, None otherwise.
        """
        self._ensure_loaded()
        return self._formulas.get(formula_id)

    def get_by_name(self, name: str) -> Optional[StoredFormula]:
        """Get a formula by name.

        Args:
            name: Formula name.

        Returns:
            StoredFormula if found, None otherwise.
        """
        self._ensure_loaded()
        name_lower = name.lower()
        for formula in self._formulas.values():
            if formula.name.lower() == name_lower:
                return formula
        return None

    def list_all(self) -> list[StoredFormula]:
        """List all formulas in the library.

        Returns:
            List of all formulas.
        """
        self._ensure_loaded()
        return sorted(
            self._formulas.values(),
            key=lambda f: f.updated_at,
            reverse=True,
        )

    def search(self, query: str) -> list[StoredFormula]:
        """Search formulas by name or tags.

        Args:
            query: Search query.

        Returns:
            List of matching formulas.
        """
        self._ensure_loaded()
        query_lower = query.lower()
        results = []

        for formula in self._formulas.values():
            if query_lower in formula.name.lower():
                results.append(formula)
            elif formula.description and query_lower in formula.description.lower():
                results.append(formula)
            elif any(query_lower in tag.lower() for tag in formula.tags):
                results.append(formula)

        return sorted(results, key=lambda f: f.updated_at, reverse=True)

    def delete(self, formula_id: str) -> bool:
        """Delete a formula from the library.

        Args:
            formula_id: Formula ID.

        Returns:
            True if deleted, False if not found.
        """
        self._ensure_loaded()

        if formula_id in self._formulas:
            del self._formulas[formula_id]
            self._save_index()
            return True
        return False

    def update_compliance_status(
        self,
        formula_id: str,
        status: str,
    ) -> Optional[StoredFormula]:
        """Update the compliance status of a formula.

        Args:
            formula_id: Formula ID.
            status: Compliance status (e.g., "compliant", "non-compliant").

        Returns:
            Updated formula if found, None otherwise.
        """
        self._ensure_loaded()

        if formula_id in self._formulas:
            formula = self._formulas[formula_id]
            formula.compliance_status = status
            formula.last_checked = datetime.now().isoformat()
            formula.updated_at = datetime.now().isoformat()
            self._save_index()
            return formula
        return None

    def get_count(self) -> int:
        """Get total number of formulas.

        Returns:
            Formula count.
        """
        self._ensure_loaded()
        return len(self._formulas)

    def duplicate(self, formula_id: str, new_name: Optional[str] = None) -> Optional[StoredFormula]:
        """Duplicate an existing formula.

        Args:
            formula_id: ID of formula to duplicate.
            new_name: Name for the new formula (defaults to "Copy of <original>").

        Returns:
            New formula if original found, None otherwise.
        """
        self._ensure_loaded()

        original = self._formulas.get(formula_id)
        if not original:
            return None

        return self.save(
            name=new_name or f"Copy of {original.name}",
            ingredients=original.ingredients.copy(),
            description=original.description,
            tags=original.tags.copy(),
        )
