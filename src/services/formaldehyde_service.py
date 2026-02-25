"""Formaldehyde donor detection and compliance service."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..models.regulatory import Market, ComplianceStatus, ComplianceResult
from ..integrations.aroma_lab import FormulaData


DEFAULT_DATA_FILE = Path(__file__).parent.parent.parent / "data" / "regulatory" / "formaldehyde_donors.json"


@dataclass
class FormaldehydeDonor:
    """Formaldehyde or formaldehyde-releasing substance."""
    cas_number: str
    name: str
    inci_name: str
    donor_type: str  # "direct", "donor", "non_donor"
    releases_formaldehyde: bool
    eu_status: str  # "restricted", "banned"
    eu_limit_percent: Optional[float] = None
    canada_status: Optional[str] = None
    labeling_threshold: Optional[float] = None
    notes: Optional[str] = None


@dataclass
class FormaldehydeResult:
    """Result of formaldehyde donor check for an ingredient."""
    cas_number: str
    name: str
    percentage: float
    is_donor: bool
    donor_type: str
    eu_status: str
    eu_limit: Optional[float]
    exceeds_limit: bool
    requires_labeling: bool
    notes: Optional[str] = None


@dataclass
class FormaldehydeReport:
    """Full formaldehyde compliance report."""
    formula_name: str
    detected_donors: list[FormaldehydeResult]
    total_formaldehyde_potential: float  # Estimated based on donor concentrations
    requires_labeling: bool
    has_banned_substances: bool
    has_violations: bool


class FormaldehydeService:
    """Service for formaldehyde donor detection and compliance."""

    def __init__(self, data_file: Optional[Path] = None):
        """Initialize the service."""
        self.data_file = data_file or DEFAULT_DATA_FILE
        self._donors: dict[str, FormaldehydeDonor] = {}
        self._labeling_threshold = 0.05  # 0.05% = 500 ppm
        self._loaded = False

    def load(self) -> None:
        """Load formaldehyde donor data from JSON file."""
        if not self.data_file.exists():
            return

        with open(self.data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data.get("formaldehyde_donors", []):
            donor = FormaldehydeDonor(
                cas_number=item.get("cas_number", ""),
                name=item.get("name", ""),
                inci_name=item.get("inci_name", ""),
                donor_type=item.get("type", "unknown"),
                releases_formaldehyde=item.get("releases_formaldehyde", False),
                eu_status=item.get("eu_status", ""),
                eu_limit_percent=item.get("eu_limit_percent"),
                canada_status=item.get("canada_status"),
                labeling_threshold=item.get("labeling_threshold"),
                notes=item.get("notes"),
            )
            self._donors[donor.cas_number] = donor

        # Get labeling threshold from config
        testing = data.get("testing_requirements", {})
        self._labeling_threshold = testing.get("labeling_trigger_eu", 0.05)

        self._loaded = True

    def _ensure_loaded(self) -> None:
        """Ensure data is loaded."""
        if not self._loaded:
            self.load()

    def get_donor(self, cas_number: str) -> Optional[FormaldehydeDonor]:
        """Get formaldehyde donor info by CAS number."""
        self._ensure_loaded()
        return self._donors.get(cas_number)

    def is_formaldehyde_donor(self, cas_number: str) -> bool:
        """Check if a CAS number is a formaldehyde donor."""
        donor = self.get_donor(cas_number)
        if donor:
            return donor.releases_formaldehyde or donor.donor_type == "direct"
        return False

    def check_formula(
        self,
        formula: FormulaData,
        markets: list[Market],
        fragrance_concentration: float = 100.0,
    ) -> FormaldehydeReport:
        """Check formula for formaldehyde donors.

        Args:
            formula: Formula to check.
            markets: Target markets.
            fragrance_concentration: Fragrance % in final product.

        Returns:
            FormaldehydeReport with detection results.
        """
        self._ensure_loaded()

        detected: list[FormaldehydeResult] = []
        total_potential = 0.0
        has_banned = False
        has_violations = False

        for ing in formula.ingredients:
            donor = self.get_donor(ing.cas_number)
            if not donor:
                continue

            # Calculate actual concentration in final product
            actual_conc = ing.percentage * (fragrance_concentration / 100.0)

            # Check if exceeds limit
            exceeds = False
            if donor.eu_limit_percent and actual_conc > donor.eu_limit_percent:
                exceeds = True
                has_violations = True

            # Check if banned
            if donor.eu_status == "banned" and Market.EU in markets:
                has_banned = True
                has_violations = True

            # Check labeling requirement
            requires_label = actual_conc >= self._labeling_threshold

            # Estimate formaldehyde potential (simplified)
            if donor.releases_formaldehyde:
                # Rough estimate: donors release ~0.1-0.5% of their weight as formaldehyde
                total_potential += actual_conc * 0.2

            detected.append(FormaldehydeResult(
                cas_number=ing.cas_number,
                name=ing.name,
                percentage=actual_conc,
                is_donor=donor.releases_formaldehyde,
                donor_type=donor.donor_type,
                eu_status=donor.eu_status,
                eu_limit=donor.eu_limit_percent,
                exceeds_limit=exceeds,
                requires_labeling=requires_label,
                notes=donor.notes,
            ))

        return FormaldehydeReport(
            formula_name=formula.name,
            detected_donors=detected,
            total_formaldehyde_potential=total_potential,
            requires_labeling=any(d.requires_labeling for d in detected),
            has_banned_substances=has_banned,
            has_violations=has_violations,
        )

    def get_compliance_results(
        self,
        formula: FormulaData,
        markets: list[Market],
        fragrance_concentration: float = 100.0,
    ) -> list[ComplianceResult]:
        """Get compliance results for formaldehyde donors.

        Args:
            formula: Formula to check.
            markets: Target markets.
            fragrance_concentration: Fragrance % in final product.

        Returns:
            List of ComplianceResult objects.
        """
        report = self.check_formula(formula, markets, fragrance_concentration)
        results: list[ComplianceResult] = []

        for donor in report.detected_donors:
            if donor.eu_status == "banned" and Market.EU in markets:
                results.append(ComplianceResult(
                    requirement="EU Formaldehyde Donor Ban",
                    status=ComplianceStatus.NON_COMPLIANT,
                    market=Market.EU,
                    details=f"{donor.name} is banned in EU cosmetics",
                    cas_number=donor.cas_number,
                    ingredient_name=donor.name,
                    current_value=donor.percentage,
                    limit_value=0.0,
                    regulation_reference="EC 1223/2009 Annex II",
                ))
            elif donor.exceeds_limit:
                results.append(ComplianceResult(
                    requirement="Formaldehyde Donor Limit",
                    status=ComplianceStatus.NON_COMPLIANT,
                    market=Market.EU,
                    details=f"{donor.name} at {donor.percentage:.4f}% exceeds limit of {donor.eu_limit}%",
                    cas_number=donor.cas_number,
                    ingredient_name=donor.name,
                    current_value=donor.percentage,
                    limit_value=donor.eu_limit,
                    regulation_reference="EC 1223/2009 Annex V",
                ))
            elif donor.requires_labeling:
                results.append(ComplianceResult(
                    requirement="Formaldehyde Labeling Required",
                    status=ComplianceStatus.WARNING,
                    market=Market.EU,
                    details=f"{donor.name} releases formaldehyde - label required 'contains formaldehyde'",
                    cas_number=donor.cas_number,
                    ingredient_name=donor.name,
                    current_value=donor.percentage,
                    limit_value=self._labeling_threshold,
                    regulation_reference="EC 1223/2009 Annex V",
                ))

        return results
