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
class VersionChange:
    """A single change in a version."""
    change_type: str  # "added", "removed", "modified", "renamed"
    field: str  # "ingredient", "name", "description", etc.
    details: str  # Human-readable description
    old_value: Optional[str] = None
    new_value: Optional[str] = None


@dataclass
class FormulaVersion:
    """A version snapshot of a formula."""
    version: int
    timestamp: str
    changes: list[dict]  # List of VersionChange as dicts
    snapshot: dict  # Full formula state at this version
    change_summary: str  # Brief summary of changes

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "changes": self.changes,
            "snapshot": self.snapshot,
            "change_summary": self.change_summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FormulaVersion":
        return cls(
            version=data.get("version", 1),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            changes=data.get("changes", []),
            snapshot=data.get("snapshot", {}),
            change_summary=data.get("change_summary", ""),
        )


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
    current_version: int = 1
    version_history: list[dict] = field(default_factory=list)

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
            "current_version": self.current_version,
            "version_history": self.version_history,
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
            current_version=data.get("current_version", 1),
            version_history=data.get("version_history", []),
        )

    def get_version_history(self) -> list[FormulaVersion]:
        """Get version history as FormulaVersion objects."""
        return [FormulaVersion.from_dict(v) for v in self.version_history]

    def get_version(self, version_num: int) -> Optional[FormulaVersion]:
        """Get a specific version."""
        for v in self.version_history:
            if v.get("version") == version_num:
                return FormulaVersion.from_dict(v)
        return None


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

    def _detect_changes(
        self,
        old_formula: StoredFormula,
        new_name: str,
        new_ingredients: list[dict],
        new_description: Optional[str],
    ) -> list[dict]:
        """Detect changes between old and new formula state.

        Returns:
            List of change dicts describing what changed.
        """
        changes = []

        # Check name change
        if old_formula.name != new_name:
            changes.append({
                "change_type": "modified",
                "field": "name",
                "details": f"Renamed from '{old_formula.name}' to '{new_name}'",
                "old_value": old_formula.name,
                "new_value": new_name,
            })

        # Check description change
        if old_formula.description != new_description:
            changes.append({
                "change_type": "modified",
                "field": "description",
                "details": "Description updated",
                "old_value": old_formula.description or "",
                "new_value": new_description or "",
            })

        # Check ingredient changes
        old_ingredients = {ing.get("cas_number"): ing for ing in old_formula.ingredients}
        new_ingredients_map = {ing.get("cas_number"): ing for ing in new_ingredients}

        # Find added ingredients
        for cas, ing in new_ingredients_map.items():
            if cas not in old_ingredients:
                changes.append({
                    "change_type": "added",
                    "field": "ingredient",
                    "details": f"Added {ing.get('name', cas)} at {ing.get('percentage', 0):.2f}%",
                    "new_value": f"{ing.get('name')} ({cas}): {ing.get('percentage')}%",
                })

        # Find removed ingredients
        for cas, ing in old_ingredients.items():
            if cas not in new_ingredients_map:
                changes.append({
                    "change_type": "removed",
                    "field": "ingredient",
                    "details": f"Removed {ing.get('name', cas)}",
                    "old_value": f"{ing.get('name')} ({cas}): {ing.get('percentage')}%",
                })

        # Find modified ingredients (percentage changed)
        for cas, new_ing in new_ingredients_map.items():
            if cas in old_ingredients:
                old_ing = old_ingredients[cas]
                old_pct = old_ing.get("percentage", 0)
                new_pct = new_ing.get("percentage", 0)
                if abs(old_pct - new_pct) > 0.0001:  # Allow for floating point
                    changes.append({
                        "change_type": "modified",
                        "field": "ingredient",
                        "details": f"{new_ing.get('name', cas)}: {old_pct:.2f}% → {new_pct:.2f}%",
                        "old_value": f"{old_pct:.4f}%",
                        "new_value": f"{new_pct:.4f}%",
                    })

        return changes

    def _create_version_snapshot(
        self,
        name: str,
        ingredients: list[dict],
        description: Optional[str],
        tags: list[str],
    ) -> dict:
        """Create a snapshot of the formula state."""
        return {
            "name": name,
            "ingredients": ingredients.copy(),
            "description": description,
            "tags": tags.copy() if tags else [],
        }

    def _generate_change_summary(self, changes: list[dict]) -> str:
        """Generate a brief summary of changes."""
        if not changes:
            return "No changes"

        added = sum(1 for c in changes if c["change_type"] == "added" and c["field"] == "ingredient")
        removed = sum(1 for c in changes if c["change_type"] == "removed" and c["field"] == "ingredient")
        modified = sum(1 for c in changes if c["change_type"] == "modified" and c["field"] == "ingredient")
        name_changed = any(c["field"] == "name" for c in changes)

        parts = []
        if name_changed:
            parts.append("renamed")
        if added:
            parts.append(f"{added} ingredient{'s' if added > 1 else ''} added")
        if removed:
            parts.append(f"{removed} ingredient{'s' if removed > 1 else ''} removed")
        if modified:
            parts.append(f"{modified} ingredient{'s' if modified > 1 else ''} modified")

        return ", ".join(parts) if parts else "Minor changes"

    def save(
        self,
        name: str,
        ingredients: list[dict],
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        formula_id: Optional[str] = None,
    ) -> StoredFormula:
        """Save a formula to the library with automatic version logging.

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
            # Update existing formula - log version change
            formula = self._formulas[formula_id]

            # Detect what changed
            changes = self._detect_changes(formula, name, ingredients, description)

            if changes:
                # Create version entry for the PREVIOUS state before updating
                new_version = formula.current_version + 1
                version_entry = FormulaVersion(
                    version=formula.current_version,
                    timestamp=formula.updated_at,
                    changes=[],  # Previous version has no "changes" - it's the baseline
                    snapshot=self._create_version_snapshot(
                        formula.name,
                        formula.ingredients,
                        formula.description,
                        formula.tags,
                    ),
                    change_summary="Snapshot before update",
                )

                # Add to history if this is the first version entry
                if not formula.version_history:
                    formula.version_history.append(version_entry.to_dict())

                # Create new version entry for the NEW state
                new_version_entry = FormulaVersion(
                    version=new_version,
                    timestamp=now,
                    changes=changes,
                    snapshot=self._create_version_snapshot(name, ingredients, description, tags or []),
                    change_summary=self._generate_change_summary(changes),
                )
                formula.version_history.append(new_version_entry.to_dict())
                formula.current_version = new_version

            # Update the formula
            formula.name = name
            formula.ingredients = ingredients
            formula.updated_at = now
            formula.description = description
            formula.tags = tags or []
        else:
            # Create new formula - version 1
            formula = StoredFormula(
                id=str(uuid.uuid4()),
                name=name,
                ingredients=ingredients,
                created_at=now,
                updated_at=now,
                description=description,
                tags=tags or [],
                current_version=1,
                version_history=[
                    FormulaVersion(
                        version=1,
                        timestamp=now,
                        changes=[{"change_type": "created", "field": "formula", "details": "Initial creation"}],
                        snapshot=self._create_version_snapshot(name, ingredients, description, tags or []),
                        change_summary="Initial version",
                    ).to_dict()
                ],
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

    def get_version_history(self, formula_id: str) -> list[FormulaVersion]:
        """Get the version history for a formula.

        Args:
            formula_id: Formula ID.

        Returns:
            List of FormulaVersion objects, newest first.
        """
        self._ensure_loaded()

        formula = self._formulas.get(formula_id)
        if not formula:
            return []

        versions = formula.get_version_history()
        return sorted(versions, key=lambda v: v.version, reverse=True)

    def get_version_snapshot(self, formula_id: str, version_num: int) -> Optional[dict]:
        """Get the formula snapshot at a specific version.

        Args:
            formula_id: Formula ID.
            version_num: Version number to retrieve.

        Returns:
            Formula snapshot dict if found, None otherwise.
        """
        self._ensure_loaded()

        formula = self._formulas.get(formula_id)
        if not formula:
            return None

        version = formula.get_version(version_num)
        if version:
            return version.snapshot
        return None

    def restore_version(self, formula_id: str, version_num: int) -> Optional[StoredFormula]:
        """Restore a formula to a previous version.

        This creates a new version entry with the restored state.

        Args:
            formula_id: Formula ID.
            version_num: Version number to restore to.

        Returns:
            Updated formula if successful, None otherwise.
        """
        self._ensure_loaded()

        formula = self._formulas.get(formula_id)
        if not formula:
            return None

        version = formula.get_version(version_num)
        if not version:
            return None

        snapshot = version.snapshot

        # Save with restored values (this will create a new version entry)
        return self.save(
            name=snapshot.get("name", formula.name),
            ingredients=snapshot.get("ingredients", []),
            description=snapshot.get("description"),
            tags=snapshot.get("tags", []),
            formula_id=formula_id,
        )

    def compare_versions(
        self,
        formula_id: str,
        version_a: int,
        version_b: int,
    ) -> dict:
        """Compare two versions of a formula.

        Args:
            formula_id: Formula ID.
            version_a: First version number.
            version_b: Second version number.

        Returns:
            Dict with comparison results.
        """
        self._ensure_loaded()

        formula = self._formulas.get(formula_id)
        if not formula:
            return {"error": "Formula not found"}

        snapshot_a = self.get_version_snapshot(formula_id, version_a)
        snapshot_b = self.get_version_snapshot(formula_id, version_b)

        if not snapshot_a or not snapshot_b:
            return {"error": "One or both versions not found"}

        # Compare ingredients
        ing_a = {i.get("cas_number"): i for i in snapshot_a.get("ingredients", [])}
        ing_b = {i.get("cas_number"): i for i in snapshot_b.get("ingredients", [])}

        added = []
        removed = []
        modified = []

        for cas, ing in ing_b.items():
            if cas not in ing_a:
                added.append(ing)
            else:
                old_pct = ing_a[cas].get("percentage", 0)
                new_pct = ing.get("percentage", 0)
                if abs(old_pct - new_pct) > 0.0001:
                    modified.append({
                        "ingredient": ing,
                        "old_percentage": old_pct,
                        "new_percentage": new_pct,
                    })

        for cas, ing in ing_a.items():
            if cas not in ing_b:
                removed.append(ing)

        return {
            "version_a": version_a,
            "version_b": version_b,
            "name_changed": snapshot_a.get("name") != snapshot_b.get("name"),
            "old_name": snapshot_a.get("name"),
            "new_name": snapshot_b.get("name"),
            "ingredients_added": added,
            "ingredients_removed": removed,
            "ingredients_modified": modified,
        }
