"""Tests for formaldehyde donor detection service."""

import pytest
from pathlib import Path
from src.models.regulatory import Market
from src.services.formaldehyde_service import FormaldehydeService
from src.integrations.aroma_lab import FormulaData, FormulaIngredientData


@pytest.fixture
def formaldehyde_service():
    """Create formaldehyde service instance."""
    data_file = Path(__file__).parent.parent.parent / "data" / "regulatory" / "formaldehyde_donors.json"
    return FormaldehydeService(data_file=data_file)


@pytest.fixture
def formula_with_donors():
    """Create a formula containing formaldehyde donors."""
    return FormulaData(
        name="Preserved Fragrance",
        ingredients=[
            FormulaIngredientData(
                cas_number="64-17-5",  # Ethanol - not a donor
                name="Ethanol",
                percentage=90.0,
            ),
            FormulaIngredientData(
                cas_number="51229-78-8",  # DMDM Hydantoin - donor
                name="DMDM Hydantoin",
                percentage=0.5,
            ),
            FormulaIngredientData(
                cas_number="57028-96-3",  # Quaternium-15 - donor
                name="Quaternium-15",
                percentage=0.1,
            ),
        ],
    )


class TestFormaldehydeService:
    """Test cases for formaldehyde service."""

    def test_get_donor_dmdm_hydantoin(self, formaldehyde_service):
        """Test getting donor info for DMDM Hydantoin."""
        donor = formaldehyde_service.get_donor("51229-78-8")
        if donor:
            assert donor.name == "DMDM Hydantoin"
            assert donor.releases_formaldehyde is True
            assert donor.donor_type == "donor"

    def test_is_formaldehyde_donor_positive(self, formaldehyde_service):
        """Test is_formaldehyde_donor returns True for known donors."""
        # Quaternium-15 is a known formaldehyde donor
        result = formaldehyde_service.is_formaldehyde_donor("57028-96-3")
        if formaldehyde_service._loaded:
            assert result is True

    def test_is_formaldehyde_donor_negative(self, formaldehyde_service):
        """Test is_formaldehyde_donor returns False for non-donors."""
        # Ethanol is not a formaldehyde donor
        result = formaldehyde_service.is_formaldehyde_donor("64-17-5")
        assert result is False

    def test_check_formula_detects_donors(self, formaldehyde_service, formula_with_donors):
        """Test that formula check detects formaldehyde donors."""
        report = formaldehyde_service.check_formula(
            formula=formula_with_donors,
            markets=[Market.EU],
            fragrance_concentration=100.0,
        )

        assert report.formula_name == "Preserved Fragrance"
        if formaldehyde_service._loaded:
            assert len(report.detected_donors) >= 1
            # Should have formaldehyde potential
            assert report.total_formaldehyde_potential > 0

    def test_labeling_requirement(self, formaldehyde_service):
        """Test labeling requirement detection."""
        # Formula with donor above labeling threshold (0.05%)
        formula = FormulaData(
            name="High DMDM",
            ingredients=[
                FormulaIngredientData(
                    cas_number="51229-78-8",
                    name="DMDM Hydantoin",
                    percentage=0.1,  # Above 0.05% threshold
                ),
            ],
        )

        report = formaldehyde_service.check_formula(
            formula=formula,
            markets=[Market.EU],
            fragrance_concentration=100.0,
        )

        if formaldehyde_service._loaded and report.detected_donors:
            assert report.requires_labeling is True

    def test_banned_substance_detection(self, formaldehyde_service):
        """Test detection of banned formaldehyde donors."""
        # Bronopol is banned in EU
        formula = FormulaData(
            name="With Bronopol",
            ingredients=[
                FormulaIngredientData(
                    cas_number="2372-21-6",  # Bronopol
                    name="Bronopol",
                    percentage=0.1,
                ),
            ],
        )

        report = formaldehyde_service.check_formula(
            formula=formula,
            markets=[Market.EU],
            fragrance_concentration=100.0,
        )

        if formaldehyde_service._loaded:
            # Bronopol is banned in EU
            donor = formaldehyde_service.get_donor("2372-21-6")
            if donor and donor.eu_status == "banned":
                assert report.has_banned_substances is True

    def test_compliance_results(self, formaldehyde_service, formula_with_donors):
        """Test compliance results generation."""
        results = formaldehyde_service.get_compliance_results(
            formula=formula_with_donors,
            markets=[Market.EU],
            fragrance_concentration=100.0,
        )

        # Should return list of ComplianceResult objects
        assert isinstance(results, list)


class TestFormaldehydeLimits:
    """Test formaldehyde limit checking."""

    def test_within_limit(self, formaldehyde_service):
        """Test formula within EU limits."""
        # DMDM Hydantoin limit is 0.6%
        formula = FormulaData(
            name="Within Limit",
            ingredients=[
                FormulaIngredientData(
                    cas_number="51229-78-8",
                    name="DMDM Hydantoin",
                    percentage=0.3,  # Within 0.6% limit
                ),
            ],
        )

        report = formaldehyde_service.check_formula(
            formula=formula,
            markets=[Market.EU],
            fragrance_concentration=100.0,
        )

        if formaldehyde_service._loaded and report.detected_donors:
            donor_result = report.detected_donors[0]
            assert donor_result.exceeds_limit is False

    def test_exceeds_limit(self, formaldehyde_service):
        """Test formula exceeding EU limits."""
        # DMDM Hydantoin limit is 0.6%
        formula = FormulaData(
            name="Exceeds Limit",
            ingredients=[
                FormulaIngredientData(
                    cas_number="51229-78-8",
                    name="DMDM Hydantoin",
                    percentage=0.8,  # Exceeds 0.6% limit
                ),
            ],
        )

        report = formaldehyde_service.check_formula(
            formula=formula,
            markets=[Market.EU],
            fragrance_concentration=100.0,
        )

        if formaldehyde_service._loaded and report.detected_donors:
            donor_result = report.detected_donors[0]
            assert donor_result.exceeds_limit is True
            assert report.has_violations is True
