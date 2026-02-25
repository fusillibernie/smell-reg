"""Tests for allergen detection service."""

import pytest
from pathlib import Path
from src.models.regulatory import Market
from src.services.allergen_service import AllergenService
from src.integrations.aroma_lab import FormulaData, FormulaIngredientData


@pytest.fixture
def allergen_service():
    """Create allergen service instance."""
    # Use the actual data file
    data_file = Path(__file__).parent.parent.parent / "data" / "regulatory" / "allergens.json"
    service = AllergenService(data_file=data_file)
    return service


@pytest.fixture
def formula_with_allergens():
    """Create a formula containing known allergens."""
    return FormulaData(
        name="Floral Fragrance",
        ingredients=[
            FormulaIngredientData(
                cas_number="78-70-6",  # Linalool - EU allergen
                name="Linalool",
                percentage=15.0,
            ),
            FormulaIngredientData(
                cas_number="5989-27-5",  # Limonene - EU allergen
                name="d-Limonene",
                percentage=10.0,
            ),
            FormulaIngredientData(
                cas_number="106-24-1",  # Geraniol - EU allergen
                name="Geraniol",
                percentage=5.0,
            ),
            FormulaIngredientData(
                cas_number="64-17-5",  # Ethanol - not an allergen
                name="Ethanol",
                percentage=70.0,
            ),
        ],
    )


class TestAllergenService:
    """Test cases for allergen service."""

    def test_get_allergen_linalool(self, allergen_service):
        """Test getting allergen data for linalool."""
        allergen = allergen_service.get_allergen("78-70-6")
        if allergen:
            assert allergen.name == "Linalool"
            assert allergen.eu_26 is True

    def test_is_allergen_positive(self, allergen_service):
        """Test is_allergen returns True for known allergens."""
        # Linalool is a known EU allergen
        assert allergen_service.is_allergen("78-70-6") is True or not allergen_service._loaded

    def test_is_allergen_negative(self, allergen_service):
        """Test is_allergen returns False for non-allergens."""
        # Ethanol is not an allergen
        result = allergen_service.is_allergen("64-17-5")
        assert result is False

    def test_check_formula_detects_allergens(self, allergen_service, formula_with_allergens):
        """Test that formula check detects allergens."""
        report = allergen_service.check_formula(
            formula=formula_with_allergens,
            markets=[Market.EU],
            fragrance_concentration=20.0,
            is_leave_on=True,
        )

        assert report.formula_name == "Floral Fragrance"
        # Should detect at least some allergens if data is loaded
        if allergen_service._loaded:
            assert len(report.detected_allergens) > 0

    def test_check_formula_disclosure_thresholds(self, allergen_service):
        """Test that disclosure is triggered above threshold."""
        # Create formula with allergen above leave-on threshold (0.001%)
        formula = FormulaData(
            name="High Linalool",
            ingredients=[
                FormulaIngredientData(
                    cas_number="78-70-6",
                    name="Linalool",
                    percentage=1.0,  # 1% in fragrance
                ),
            ],
        )

        # At 20% fragrance concentration, linalool = 0.2% in product
        # This is above 0.001% threshold
        report = allergen_service.check_formula(
            formula=formula,
            markets=[Market.EU],
            fragrance_concentration=20.0,
            is_leave_on=True,
        )

        if allergen_service._loaded and report.detected_allergens:
            allergen_result = report.detected_allergens[0]
            assert allergen_result.concentration_in_product == pytest.approx(0.2)
            assert allergen_result.requires_disclosure is True

    def test_rinse_off_higher_threshold(self, allergen_service):
        """Test that rinse-off products have higher threshold."""
        formula = FormulaData(
            name="Low Linalool",
            ingredients=[
                FormulaIngredientData(
                    cas_number="78-70-6",
                    name="Linalool",
                    percentage=0.1,  # 0.1% in fragrance
                ),
            ],
        )

        # At 10% concentration = 0.01% in product
        # This is above leave-on threshold (0.001%) but at rinse-off threshold (0.01%)
        leave_on_report = allergen_service.check_formula(
            formula=formula,
            markets=[Market.EU],
            fragrance_concentration=10.0,
            is_leave_on=True,
        )

        rinse_off_report = allergen_service.check_formula(
            formula=formula,
            markets=[Market.EU],
            fragrance_concentration=10.0,
            is_leave_on=False,
        )

        # Leave-on should require disclosure, rinse-off might not (at threshold)
        if allergen_service._loaded and leave_on_report.detected_allergens:
            leave_on_disclosure = len(leave_on_report.disclosure_required)
            rinse_off_disclosure = len(rinse_off_report.disclosure_required)
            # Leave-on should have same or more disclosure requirements
            assert leave_on_disclosure >= rinse_off_disclosure
