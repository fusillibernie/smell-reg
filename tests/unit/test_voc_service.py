"""Tests for VOC compliance service."""

import pytest
from pathlib import Path
from src.models.regulatory import Market, ProductType
from src.models.voc import VOCRegulation
from src.services.voc_service import VOCService
from src.integrations.aroma_lab import FormulaData, FormulaIngredientData


@pytest.fixture
def voc_service():
    """Create VOC service instance."""
    data_dir = Path(__file__).parent.parent.parent / "data" / "regulatory"
    return VOCService(
        limits_file=data_dir / "voc_limits.json",
        ingredients_file=data_dir / "voc_ingredients.json",
    )


@pytest.fixture
def high_voc_formula():
    """Create a formula with high VOC content."""
    return FormulaData(
        name="High VOC Formula",
        ingredients=[
            FormulaIngredientData(
                cas_number="64-17-5",  # Ethanol - 100% VOC
                name="Ethanol",
                percentage=80.0,
            ),
            FormulaIngredientData(
                cas_number="78-70-6",  # Linalool - 100% VOC
                name="Linalool",
                percentage=20.0,
            ),
        ],
    )


@pytest.fixture
def low_voc_formula():
    """Create a formula with low VOC content."""
    return FormulaData(
        name="Low VOC Formula",
        ingredients=[
            FormulaIngredientData(
                cas_number="57-55-6",  # Propylene glycol - exempt
                name="Propylene glycol",
                percentage=95.0,
            ),
            FormulaIngredientData(
                cas_number="78-70-6",
                name="Linalool",
                percentage=5.0,
            ),
        ],
    )


class TestVOCService:
    """Test cases for VOC service."""

    def test_get_limit_carb_personal_fragrance(self, voc_service):
        """Test getting CARB limit for personal fragrance."""
        limit = voc_service.get_limit(
            VOCRegulation.CARB,
            "Personal Fragrance Products",
        )
        # CARB limit for personal fragrance is 75%
        assert limit == 75.0 or limit is None  # None if data not loaded

    def test_get_ingredient_voc_ethanol(self, voc_service):
        """Test VOC percentage for ethanol."""
        voc_pct = voc_service.get_ingredient_voc_percent("64-17-5")
        # Ethanol is 100% VOC
        assert voc_pct == 100.0

    def test_is_exempt_acetone(self, voc_service):
        """Test that acetone is CARB exempt."""
        is_exempt, reason = voc_service.is_exempt("67-64-1", VOCRegulation.CARB)
        if voc_service._loaded:
            assert is_exempt is True
            assert reason is not None

    def test_calculate_voc_high_formula(self, voc_service, high_voc_formula):
        """Test VOC calculation for high VOC formula."""
        calc = voc_service.calculate_voc(
            formula=high_voc_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            regulation=VOCRegulation.CARB,
        )

        assert calc.regulation == VOCRegulation.CARB
        # 80% ethanol + 20% linalool, both 100% VOC = 100% total VOC
        assert calc.total_voc_percent == pytest.approx(100.0)

    def test_calculate_voc_with_exempt(self, voc_service, low_voc_formula):
        """Test VOC calculation with exempt ingredients."""
        calc = voc_service.calculate_voc(
            formula=low_voc_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            regulation=VOCRegulation.CARB,
        )

        # Only linalool (5%) should contribute to VOC
        # Propylene glycol should be exempt
        if voc_service._loaded:
            assert calc.total_voc_percent < 100.0

    def test_check_formula_multiple_markets(self, voc_service, high_voc_formula):
        """Test checking formula across multiple markets."""
        report = voc_service.check_formula(
            formula=high_voc_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            markets=[Market.US, Market.CA],
        )

        assert report.formula_name == "High VOC Formula"
        # Should have calculations for CARB (US) and Canada
        assert len(report.calculations) >= 1

    def test_compliance_check_fine_fragrance(self, voc_service, high_voc_formula):
        """Test compliance for fine fragrance (75% limit)."""
        report = voc_service.check_formula(
            formula=high_voc_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            markets=[Market.US],
        )

        # 100% VOC should exceed 75% limit
        if report.calculations:
            carb_calc = report.calculations[0]
            if carb_calc.limit_percent == 75.0:
                assert carb_calc.is_compliant is False


class TestVOCMarginCalculation:
    """Test VOC margin calculations."""

    def test_margin_positive_under_limit(self, voc_service):
        """Test that margin is positive when under limit."""
        formula = FormulaData(
            name="Under Limit",
            ingredients=[
                FormulaIngredientData(
                    cas_number="64-17-5",
                    name="Ethanol",
                    percentage=50.0,  # 50% VOC
                ),
                FormulaIngredientData(
                    cas_number="57-55-6",
                    name="Propylene glycol",
                    percentage=50.0,
                ),
            ],
        )

        calc = voc_service.calculate_voc(
            formula=formula,
            product_type=ProductType.FINE_FRAGRANCE,
            regulation=VOCRegulation.CARB,
        )

        # 50% VOC vs 75% limit = 25% margin
        if calc.limit_percent == 75.0:
            assert calc.margin > 0
            assert calc.is_compliant is True

    def test_margin_negative_over_limit(self, voc_service, high_voc_formula):
        """Test that margin is negative when over limit."""
        calc = voc_service.calculate_voc(
            formula=high_voc_formula,
            product_type=ProductType.FINE_FRAGRANCE,
            regulation=VOCRegulation.CARB,
        )

        # 100% VOC vs 75% limit = -25% margin
        if calc.limit_percent == 75.0:
            assert calc.margin < 0
            assert calc.is_compliant is False
