"""Tests for IFRA compliance service."""

import pytest
from src.models.regulatory import ProductType, ComplianceStatus
from src.services.ifra_service import IFRAService
from src.integrations.aroma_lab import FormulaData, FormulaIngredientData


@pytest.fixture
def ifra_service():
    """Create IFRA service instance."""
    return IFRAService()


@pytest.fixture
def sample_formula():
    """Create a sample formula for testing."""
    return FormulaData(
        name="Test Fragrance",
        ingredients=[
            FormulaIngredientData(
                cas_number="78-70-6",
                name="Linalool",
                percentage=15.0,
            ),
            FormulaIngredientData(
                cas_number="5989-27-5",
                name="d-Limonene",
                percentage=10.0,
            ),
            FormulaIngredientData(
                cas_number="106-22-9",
                name="Citronellol",
                percentage=8.0,
            ),
        ],
    )


class TestIFRAService:
    """Test cases for IFRA service."""

    def test_get_ifra_category_fine_fragrance(self, ifra_service):
        """Test IFRA category lookup for fine fragrance."""
        category = ifra_service.get_ifra_category(ProductType.FINE_FRAGRANCE)
        assert category == "4"

    def test_get_ifra_category_candle(self, ifra_service):
        """Test IFRA category lookup for candle."""
        category = ifra_service.get_ifra_category(ProductType.CANDLE)
        assert category == "11A"

    def test_get_ifra_category_body_lotion(self, ifra_service):
        """Test IFRA category lookup for body lotion."""
        category = ifra_service.get_ifra_category(ProductType.BODY_LOTION)
        assert category == "5A"

    def test_check_compliance_returns_result(self, ifra_service, sample_formula):
        """Test that compliance check returns a result."""
        result = ifra_service.check_compliance(
            formula=sample_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            fragrance_concentration=20.0,
        )
        assert result is not None
        assert isinstance(result.is_compliant, bool)
        assert isinstance(result.violations, list)
        assert isinstance(result.warnings, list)

    def test_check_compliance_with_dilution(self, ifra_service, sample_formula):
        """Test compliance check accounts for dilution."""
        # At 100% concentration
        result_100 = ifra_service.check_compliance(
            formula=sample_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            fragrance_concentration=100.0,
        )

        # At 10% concentration
        result_10 = ifra_service.check_compliance(
            formula=sample_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            fragrance_concentration=10.0,
        )

        # Lower concentration should have fewer or same violations
        assert len(result_10.violations) <= len(result_100.violations)

    def test_certificate_number_generated_when_compliant(self, ifra_service):
        """Test that certificate number is generated for compliant formulas."""
        # Create a minimal formula likely to be compliant
        formula = FormulaData(
            name="Simple Fragrance",
            ingredients=[
                FormulaIngredientData(
                    cas_number="64-17-5",  # Ethanol - not IFRA restricted
                    name="Ethanol",
                    percentage=90.0,
                ),
                FormulaIngredientData(
                    cas_number="78-70-6",
                    name="Linalool",
                    percentage=10.0,
                ),
            ],
        )

        result = ifra_service.check_compliance(
            formula=formula,
            product_type=ProductType.FINE_FRAGRANCE,
            fragrance_concentration=10.0,  # Low concentration
        )

        if result.is_compliant:
            assert result.certificate_number is not None
            assert result.certificate_number.startswith("IFRA-")


class TestIFRACategoryMapping:
    """Test IFRA category mapping."""

    def test_all_product_types_have_category(self, ifra_service):
        """Test that most product types map to an IFRA category."""
        # These should have mappings
        mapped_types = [
            ProductType.LIP_PRODUCT,
            ProductType.DEODORANT,
            ProductType.FINE_FRAGRANCE,
            ProductType.BODY_LOTION,
            ProductType.CANDLE,
        ]

        for pt in mapped_types:
            category = ifra_service.get_ifra_category(pt)
            assert category is not None, f"{pt} should have IFRA category"
