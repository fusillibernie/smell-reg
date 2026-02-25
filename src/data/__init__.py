"""Data access layer for smell-reg."""

from .repository import (
    RegulatoryDataRepository,
    get_repository,
)

__all__ = [
    "RegulatoryDataRepository",
    "get_repository",
]
