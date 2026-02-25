"""Market-specific regulatory requirements service."""

import json
from pathlib import Path
from typing import Optional

from ..models.regulatory import Market, ProductType, ComplianceStatus, ComplianceResult
from ..integrations.aroma_lab import FormulaData


# Default data file locations
DEFAULT_PROP65_FILE = Path(__file__).parent.parent.parent / "data" / "regulatory" / "prop65.json"
DEFAULT_HOTLIST_FILE = Path(__file__).parent.parent.parent / "data" / "regulatory" / "canada_hotlist.json"
DEFAULT_REACH_FILE = Path(__file__).parent.parent.parent / "data" / "regulatory" / "reach.json"


class MarketService:
    """Service for market-specific regulatory requirements."""

    def __init__(
        self,
        prop65_file: Optional[Path] = None,
        hotlist_file: Optional[Path] = None,
        reach_file: Optional[Path] = None,
    ):
        """Initialize the service.

        Args:
            prop65_file: Path to California Prop 65 data.
            hotlist_file: Path to Canada Hotlist data.
            reach_file: Path to EU REACH data.
        """
        self.prop65_file = prop65_file or DEFAULT_PROP65_FILE
        self.hotlist_file = hotlist_file or DEFAULT_HOTLIST_FILE
        self.reach_file = reach_file or DEFAULT_REACH_FILE

        self._prop65_substances: dict[str, dict] = {}
        self._hotlist_substances: dict[str, dict] = {}
        self._reach_substances: dict[str, dict] = {}
        self._loaded = False

    def load(self) -> None:
        """Load regulatory data from JSON files."""
        # Load Prop 65
        if self.prop65_file.exists():
            with open(self.prop65_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._prop65_substances = {
                item["cas_number"]: item
                for item in data.get("substances", [])
            }

        # Load Canada Hotlist
        if self.hotlist_file.exists():
            with open(self.hotlist_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._hotlist_substances = {
                item["cas_number"]: item
                for item in data.get("substances", [])
            }

        # Load REACH
        if self.reach_file.exists():
            with open(self.reach_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._reach_substances = {
                item["cas_number"]: item
                for item in data.get("substances", [])
            }

        self._loaded = True

    def _ensure_loaded(self) -> None:
        """Ensure data is loaded."""
        if not self._loaded:
            self.load()

    def check_prop65(
        self,
        formula: FormulaData,
        fragrance_concentration: float = 100.0,
    ) -> list[ComplianceResult]:
        """Check formula for California Prop 65 compliance.

        Args:
            formula: Formula to check.
            fragrance_concentration: Fragrance % in final product.

        Returns:
            List of compliance results for Prop 65 substances.
        """
        self._ensure_loaded()
        results: list[ComplianceResult] = []

        for ing in formula.ingredients:
            if ing.cas_number in self._prop65_substances:
                sub = self._prop65_substances[ing.cas_number]
                actual_conc = ing.percentage * (fragrance_concentration / 100.0)

                # Prop 65 has NSRL (No Significant Risk Level) values
                nsrl = sub.get("nsrl_ug_day")
                warning_required = sub.get("warning_required", True)

                results.append(
                    ComplianceResult(
                        requirement="California Proposition 65",
                        status=ComplianceStatus.WARNING if warning_required else ComplianceStatus.COMPLIANT,
                        market=Market.US,
                        details=f"{ing.name} is listed under Prop 65 ({sub.get('listing_mechanism', 'unknown')})",
                        cas_number=ing.cas_number,
                        ingredient_name=ing.name,
                        current_value=actual_conc,
                        limit_value=nsrl,
                        regulation_reference="California Health & Safety Code Section 25249.6",
                    )
                )

        return results

    def check_canada_hotlist(
        self,
        formula: FormulaData,
        product_type: ProductType,
    ) -> list[ComplianceResult]:
        """Check formula against Canada Cosmetic Ingredient Hotlist.

        Args:
            formula: Formula to check.
            product_type: Product type.

        Returns:
            List of compliance results.
        """
        self._ensure_loaded()
        results: list[ComplianceResult] = []

        for ing in formula.ingredients:
            if ing.cas_number in self._hotlist_substances:
                sub = self._hotlist_substances[ing.cas_number]
                restriction_type = sub.get("restriction_type", "restricted")

                if restriction_type == "prohibited":
                    status = ComplianceStatus.NON_COMPLIANT
                    details = f"{ing.name} is prohibited in cosmetics (Health Canada Hotlist)"
                else:
                    status = ComplianceStatus.WARNING
                    limit = sub.get("limit_percent")
                    details = f"{ing.name} is restricted: {sub.get('restriction', 'see regulations')}"
                    if limit:
                        if ing.percentage > limit:
                            status = ComplianceStatus.NON_COMPLIANT
                            details = f"{ing.name} at {ing.percentage}% exceeds limit of {limit}%"

                results.append(
                    ComplianceResult(
                        requirement="Health Canada Cosmetic Ingredient Hotlist",
                        status=status,
                        market=Market.CA,
                        details=details,
                        cas_number=ing.cas_number,
                        ingredient_name=ing.name,
                        current_value=ing.percentage,
                        limit_value=sub.get("limit_percent"),
                        regulation_reference="Cosmetic Regulations (C.R.C., c. 869)",
                    )
                )

        return results

    def check_reach(
        self,
        formula: FormulaData,
        fragrance_concentration: float = 100.0,
    ) -> list[ComplianceResult]:
        """Check formula for EU REACH compliance.

        Args:
            formula: Formula to check.
            fragrance_concentration: Fragrance % in final product.

        Returns:
            List of compliance results.
        """
        self._ensure_loaded()
        results: list[ComplianceResult] = []

        for ing in formula.ingredients:
            if ing.cas_number in self._reach_substances:
                sub = self._reach_substances[ing.cas_number]
                actual_conc = ing.percentage * (fragrance_concentration / 100.0)

                # Check SVHC (Substances of Very High Concern)
                if sub.get("svhc", False):
                    results.append(
                        ComplianceResult(
                            requirement="REACH SVHC Notification",
                            status=ComplianceStatus.WARNING,
                            market=Market.EU,
                            details=f"{ing.name} is an SVHC requiring notification above 0.1%",
                            cas_number=ing.cas_number,
                            ingredient_name=ing.name,
                            current_value=actual_conc,
                            limit_value=0.1,
                            regulation_reference="REACH Regulation (EC) No 1907/2006",
                        )
                    )

                # Check Annex XVII restrictions
                restriction = sub.get("annex_xvii_restriction")
                if restriction:
                    limit = restriction.get("limit_percent")
                    if limit and actual_conc > limit:
                        results.append(
                            ComplianceResult(
                                requirement="REACH Annex XVII Restriction",
                                status=ComplianceStatus.NON_COMPLIANT,
                                market=Market.EU,
                                details=f"{ing.name} exceeds Annex XVII limit",
                                cas_number=ing.cas_number,
                                ingredient_name=ing.name,
                                current_value=actual_conc,
                                limit_value=limit,
                                regulation_reference="REACH Regulation Annex XVII",
                            )
                        )

        return results

    def check_market_requirements(
        self,
        formula: FormulaData,
        markets: list[Market],
        product_type: ProductType,
        fragrance_concentration: float = 100.0,
    ) -> list[ComplianceResult]:
        """Check all market-specific requirements.

        Args:
            formula: Formula to check.
            markets: Target markets.
            product_type: Product type.
            fragrance_concentration: Fragrance % in final product.

        Returns:
            Combined list of compliance results.
        """
        results: list[ComplianceResult] = []

        if Market.US in markets:
            results.extend(self.check_prop65(formula, fragrance_concentration))

        if Market.CA in markets:
            results.extend(self.check_canada_hotlist(formula, product_type))

        if Market.EU in markets or Market.UK in markets:
            results.extend(self.check_reach(formula, fragrance_concentration))

        return results
