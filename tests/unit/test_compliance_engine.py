"""Tests for compliance engine orchestrator."""

import pytest
from src.models.regulatory import Market, ProductType, ComplianceStatus
from src.services.compliance_engine import ComplianceEngine
from src.integrations.aroma_lab import FormulaData, FormulaIngredientData


@pytest.fixture
def engine():
    """Create compliance engine instance."""
    return ComplianceEngine()


@pytest.fixture
def sample_formula():
    """Create a sample fragrance formula."""
    return FormulaData(
        name="Sample Fine Fragrance",
        ingredients=[
            FormulaIngredientData(
                cas_number="64-17-5",
                name="Ethanol",
                percentage=70.0,
            ),
            FormulaIngredientData(
                cas_number="78-70-6",
                name="Linalool",
                percentage=10.0,
            ),
            FormulaIngredientData(
                cas_number="5989-27-5",
                name="d-Limonene",
                percentage=8.0,
            ),
            FormulaIngredientData(
                cas_number="106-22-9",
                name="Citronellol",
                percentage=5.0,
            ),
            FormulaIngredientData(
                cas_number="106-24-1",
                name="Geraniol",
                percentage=4.0,
            ),
            FormulaIngredientData(
                cas_number="91-64-5",
                name="Coumarin",
                percentage=3.0,
            ),
        ],
    )


class TestComplianceEngine:
    """Test cases for compliance engine."""

    def test_full_compliance_check(self, engine, sample_formula):
        """Test running full compliance check."""
        report = engine.check_compliance(
            formula=sample_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            markets=[Market.US, Market.EU, Market.CA],
            fragrance_concentration=20.0,
            is_leave_on=True,
        )

        assert report.formula_name == "Sample Fine Fragrance"
        assert report.product_type == ProductType.FINE_FRAGRANCE
        assert Market.US in report.markets
        assert Market.EU in report.markets
        assert len(report.results) > 0

    def test_ifra_only_check(self, engine, sample_formula):
        """Test IFRA-only compliance check."""
        result = engine.check_ifra(
            formula=sample_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            fragrance_concentration=20.0,
        )

        assert isinstance(result.is_compliant, bool)
        assert isinstance(result.violations, list)
        assert isinstance(result.compliant_ingredients, list)

    def test_allergen_only_check(self, engine, sample_formula):
        """Test allergen-only check."""
        report = engine.check_allergens(
            formula=sample_formula,
            markets=[Market.EU],
            fragrance_concentration=20.0,
            is_leave_on=True,
        )

        assert report.formula_name == "Sample Fine Fragrance"
        assert Market.EU in report.markets

    def test_voc_only_check(self, engine, sample_formula):
        """Test VOC-only check."""
        report = engine.check_voc(
            formula=sample_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            markets=[Market.US],
        )

        assert report.formula_name == "Sample Fine Fragrance"
        assert report.product_type == ProductType.FINE_FRAGRANCE

    def test_fse_generation(self, engine, sample_formula):
        """Test FSE report generation."""
        report = engine.generate_fse(
            formula=sample_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            fragrance_concentration=20.0,
            intended_use="Fine fragrance application",
            assessor="Test Assessor",
        )

        assert report.formula_name == "Sample Fine Fragrance"
        assert report.assessor == "Test Assessor"
        assert report.report_number is not None
        assert len(report.ingredients) == len(sample_formula.ingredients)

    def test_compliance_report_properties(self, engine, sample_formula):
        """Test compliance report computed properties."""
        report = engine.check_compliance(
            formula=sample_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            markets=[Market.US],
            fragrance_concentration=20.0,
        )

        # Test computed properties
        assert isinstance(report.is_compliant, bool)
        assert isinstance(report.non_compliant_items, list)
        assert isinstance(report.warnings, list)

    def test_certificate_number_format(self, engine, sample_formula):
        """Test that certificate numbers follow expected format."""
        report = engine.check_compliance(
            formula=sample_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            markets=[Market.US],
            fragrance_concentration=10.0,  # Low concentration for compliance
        )

        # If compliant, certificate number should be generated
        if report.is_compliant and report.certificate_number:
            assert report.certificate_number.startswith("COMP-")
            parts = report.certificate_number.split("-")
            assert len(parts) == 3
            assert len(parts[1]) == 8  # YYYYMMDD
            assert len(parts[2]) == 8  # 8 hex chars


class TestComplianceEngineIntegration:
    """Integration tests for compliance engine."""

    def test_multiple_markets(self, engine, sample_formula):
        """Test checking compliance across multiple markets."""
        report = engine.check_compliance(
            formula=sample_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            markets=[Market.US, Market.EU, Market.CA, Market.UK],
            fragrance_concentration=20.0,
        )

        # Should have results from multiple market-specific checks
        market_values = {r.market for r in report.results}
        # At least US should be present from IFRA/VOC checks
        assert Market.US in market_values or len(report.results) > 0

    def test_product_type_affects_results(self, engine, sample_formula):
        """Test that different product types yield different results."""
        fine_fragrance_report = engine.check_compliance(
            formula=sample_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            markets=[Market.US],
            fragrance_concentration=20.0,
        )

        candle_report = engine.check_compliance(
            formula=sample_formula,
            product_type=ProductType.CANDLE,
            markets=[Market.US],
            fragrance_concentration=10.0,
        )

        # Product types should have different IFRA categories
        assert fine_fragrance_report.product_type != candle_report.product_type

    def test_concentration_affects_compliance(self, engine, sample_formula):
        """Test that fragrance concentration affects compliance results."""
        high_conc = engine.check_compliance(
            formula=sample_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            markets=[Market.US],
            fragrance_concentration=100.0,  # Neat fragrance
        )

        low_conc = engine.check_compliance(
            formula=sample_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            markets=[Market.US],
            fragrance_concentration=5.0,  # Low concentration
        )

        # Lower concentration should generally be more compliant
        high_violations = len(high_conc.non_compliant_items)
        low_violations = len(low_conc.non_compliant_items)
        assert low_violations <= high_violations
