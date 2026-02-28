"""Tests for FSE (Fragrance Safety Evaluation) service."""

import pytest
from src.services.fse_service import FSEService
from src.models.fse import FSEEndpoint, RiskLevel
from src.models.regulatory import ProductType
from src.integrations.aroma_lab import FormulaData, FormulaIngredientData


@pytest.fixture
def fse_service():
    """Create FSE service instance."""
    return FSEService()


@pytest.fixture
def sample_formula():
    """Create a sample formula for testing."""
    return FormulaData(
        name="Test Fragrance",
        ingredients=[
            FormulaIngredientData(cas_number="64-17-5", name="Ethanol", percentage=70.0),
            FormulaIngredientData(cas_number="78-70-6", name="Linalool", percentage=15.0),
            FormulaIngredientData(cas_number="106-22-9", name="Citronellol", percentage=10.0),
            FormulaIngredientData(cas_number="97-53-0", name="Eugenol", percentage=5.0),
        ]
    )


class TestFSEService:
    """Tests for FSE service functionality."""

    def test_generate_fse_report(self, fse_service, sample_formula):
        """Test that FSE report is generated correctly."""
        report = fse_service.generate_fse(
            formula=sample_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            fragrance_concentration=20.0,
        )

        assert report.formula_name == "Test Fragrance"
        assert report.product_type == "fine_fragrance"
        assert report.fragrance_concentration == 20.0
        assert len(report.ingredients) == 4
        assert report.report_number is not None
        assert report.report_number.startswith("FSE-")

    def test_endpoint_summaries_generated(self, fse_service, sample_formula):
        """Test that all endpoints have summaries."""
        report = fse_service.generate_fse(
            formula=sample_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            fragrance_concentration=20.0,
        )

        # Check all endpoints are present in summaries
        for endpoint in FSEEndpoint:
            assert endpoint.value in report.endpoint_summaries

    def test_toxicity_data_used_for_assessment(self, fse_service):
        """Test that toxicity database data is used for known ingredients."""
        formula = FormulaData(
            name="Ethanol Test",
            ingredients=[
                FormulaIngredientData(cas_number="64-17-5", name="Ethanol", percentage=100.0),
            ]
        )

        report = fse_service.generate_fse(
            formula=formula,
            product_type=ProductType.FINE_FRAGRANCE,
            fragrance_concentration=100.0,
        )

        # Ethanol should have data available
        ethanol_fse = report.ingredients[0]
        assert ethanol_fse.cas_number == "64-17-5"

        # Check that assessments are not all "insufficient_data"
        risk_levels = [a.risk_level for a in ethanol_fse.assessments]
        assert RiskLevel.INSUFFICIENT_DATA not in risk_levels or \
               not all(r == RiskLevel.INSUFFICIENT_DATA for r in risk_levels)

    def test_sensitization_nesil_check(self, fse_service):
        """Test that NESIL thresholds are applied for sensitizers."""
        # Test with a known sensitizer at high concentration
        formula = FormulaData(
            name="Sensitizer Test",
            ingredients=[
                # Hexyl cinnamal has NESIL of 1.0%
                FormulaIngredientData(cas_number="101-86-0", name="Hexyl Cinnamal", percentage=5.0),
            ]
        )

        report = fse_service.generate_fse(
            formula=formula,
            product_type=ProductType.FINE_FRAGRANCE,
            fragrance_concentration=100.0,  # Full concentration
        )

        ing_fse = report.ingredients[0]
        sens_assessment = next(
            a for a in ing_fse.assessments
            if a.endpoint == FSEEndpoint.SKIN_SENSITIZATION
        )

        # At 5%, this should exceed NESIL of 1.0%
        assert sens_assessment.risk_level == RiskLevel.UNACCEPTABLE
        assert sens_assessment.threshold == 1.0

    def test_unknown_ingredient_insufficient_data(self, fse_service):
        """Test that unknown ingredients get insufficient data status."""
        formula = FormulaData(
            name="Unknown Test",
            ingredients=[
                FormulaIngredientData(cas_number="12345-67-8", name="Unknown Chemical", percentage=10.0),
            ]
        )

        report = fse_service.generate_fse(
            formula=formula,
            product_type=ProductType.FINE_FRAGRANCE,
            fragrance_concentration=100.0,
        )

        ing_fse = report.ingredients[0]
        # At least some endpoints should have insufficient data
        insufficient_count = sum(
            1 for a in ing_fse.assessments
            if a.risk_level == RiskLevel.INSUFFICIENT_DATA
        )
        assert insufficient_count > 0

    def test_banned_substance_flagged(self, fse_service):
        """Test that banned substances (like Lilial) are flagged."""
        formula = FormulaData(
            name="Lilial Test",
            ingredients=[
                # Lilial is banned in EU for reproductive toxicity
                FormulaIngredientData(cas_number="80-54-6", name="Lilial", percentage=1.0),
            ]
        )

        report = fse_service.generate_fse(
            formula=formula,
            product_type=ProductType.FINE_FRAGRANCE,
            fragrance_concentration=100.0,
        )

        ing_fse = report.ingredients[0]
        repro_assessment = next(
            a for a in ing_fse.assessments
            if a.endpoint == FSEEndpoint.REPRODUCTIVE_TOXICITY
        )

        # Lilial should be flagged as unacceptable for reproductive tox
        assert repro_assessment.risk_level == RiskLevel.UNACCEPTABLE

    def test_conclusion_reflects_risk_levels(self, fse_service):
        """Test that conclusion text reflects the actual risk levels."""
        # Safe formula
        safe_formula = FormulaData(
            name="Safe Formula",
            ingredients=[
                FormulaIngredientData(cas_number="64-17-5", name="Ethanol", percentage=100.0),
            ]
        )

        report = fse_service.generate_fse(
            formula=safe_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            fragrance_concentration=10.0,
        )

        # With a safe formula, conclusion should indicate safety
        assert "safe" in report.overall_conclusion.lower() or "acceptable" in report.overall_conclusion.lower()

    def test_exposure_parameters_applied(self, fse_service, sample_formula):
        """Test that product-specific exposure parameters are applied."""
        report = fse_service.generate_fse(
            formula=sample_formula,
            product_type=ProductType.BODY_LOTION,
            fragrance_concentration=1.0,
        )

        # Body lotion has specific exposure area
        assert report.exposure_area_cm2 == 15670
        assert report.retention_factor == 1.0

    def test_rinse_off_retention_factor(self, fse_service, sample_formula):
        """Test that rinse-off products have lower retention factors."""
        report = fse_service.generate_fse(
            formula=sample_formula,
            product_type=ProductType.SHAMPOO,
            fragrance_concentration=1.0,
        )

        # Shampoo has 0.1 retention factor
        assert report.retention_factor == 0.1

    def test_report_to_dict(self, fse_service, sample_formula):
        """Test that report can be converted to dictionary."""
        report = fse_service.generate_fse(
            formula=sample_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            fragrance_concentration=20.0,
        )

        report_dict = report.to_dict()

        assert "formula_name" in report_dict
        assert "ingredients" in report_dict
        assert "endpoint_summaries" in report_dict
        assert "overall_conclusion" in report_dict
        assert len(report_dict["ingredients"]) == 4
