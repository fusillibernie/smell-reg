"""Tests for the naturals service."""

import pytest
from pathlib import Path

from src.services.naturals_service import NaturalsService
from src.integrations.aroma_lab import FormulaData, FormulaIngredientData


class TestNaturalsService:
    """Tests for natural materials service."""

    @pytest.fixture
    def service(self):
        """Create naturals service with default data."""
        return NaturalsService()

    def test_load_naturals(self, service):
        """Test loading natural materials data."""
        service.load()
        naturals = service.get_all_naturals()
        assert len(naturals) > 0

    def test_get_lemon_oil(self, service):
        """Test getting lemon oil by CAS."""
        natural = service.get_natural("8008-56-8")
        assert natural is not None
        assert natural.name == "Lemon Oil"
        assert natural.botanical_name == "Citrus limon"

    def test_is_natural_positive(self, service):
        """Test is_natural for known natural."""
        assert service.is_natural("8008-56-8")  # Lemon oil

    def test_is_natural_negative(self, service):
        """Test is_natural for non-natural."""
        assert not service.is_natural("78-70-6")  # Linalool (isolated)

    def test_get_restricted_constituents(self, service):
        """Test getting restricted constituents from a natural."""
        natural = service.get_natural("8008-56-8")  # Lemon oil
        assert natural is not None

        # Lemon oil contains citral and limonene as restricted
        citral = natural.get_constituent("5392-40-5")
        assert citral is not None
        assert citral.name == "Citral"
        assert citral.max_percentage == 5.0

    def test_calculate_incidentals_single_natural(self, service):
        """Test calculating incidentals from a single natural."""
        formula = FormulaData(
            name="Test Formula",
            ingredients=[
                FormulaIngredientData(
                    cas_number="8008-56-8",  # Lemon oil at 10%
                    name="Lemon Oil",
                    percentage=10.0,
                ),
            ],
        )

        incidental_totals, reports = service.calculate_incidentals(formula)

        # Should have citral incidental: 5.0% max in lemon * 10% lemon = 0.5%
        assert "5392-40-5" in incidental_totals
        assert incidental_totals["5392-40-5"] == pytest.approx(0.5, rel=0.01)

        # Should have one report
        assert len(reports) == 1
        assert reports[0].natural_name == "Lemon Oil"

    def test_calculate_incidentals_multiple_naturals(self, service):
        """Test calculating incidentals from multiple naturals."""
        formula = FormulaData(
            name="Citrus Blend",
            ingredients=[
                FormulaIngredientData(
                    cas_number="8008-56-8",  # Lemon oil at 5%
                    name="Lemon Oil",
                    percentage=5.0,
                ),
                FormulaIngredientData(
                    cas_number="8007-02-1",  # Lemongrass oil at 2%
                    name="Lemongrass Oil",
                    percentage=2.0,
                ),
            ],
        )

        incidental_totals, reports = service.calculate_incidentals(formula)

        # Both contain citral:
        # Lemon: 5% max * 5% = 0.25%
        # Lemongrass: 85% max * 2% = 1.7%
        # Total: 1.95%
        assert "5392-40-5" in incidental_totals
        assert incidental_totals["5392-40-5"] == pytest.approx(1.95, rel=0.01)

        assert len(reports) == 2

    def test_get_restricted_constituent_sources(self, service):
        """Test finding sources of a restricted substance."""
        # Find all naturals containing citral
        sources = service.get_restricted_constituent_sources("5392-40-5")

        assert len(sources) > 0

        # Should include lemongrass (highest citral)
        lemongrass_found = any(n.name == "Lemongrass Oil" for n, _ in sources)
        assert lemongrass_found


class TestNaturalsServiceWithIFRA:
    """Tests for naturals service integration with IFRA."""

    def test_ifra_with_incidentals(self):
        """Test IFRA compliance check including incidentals."""
        from src.services.ifra_service import IFRAService
        from src.models.regulatory import ProductType

        ifra_service = IFRAService()

        # Formula with high lemongrass (high citral content)
        formula = FormulaData(
            name="High Citral Test",
            ingredients=[
                FormulaIngredientData(
                    cas_number="8007-02-1",  # Lemongrass oil at 10%
                    name="Lemongrass Oil",
                    percentage=10.0,
                ),
            ],
        )

        # Check compliance with incidentals
        result = ifra_service.check_compliance(
            formula,
            ProductType.FINE_FRAGRANCE,
            fragrance_concentration=20.0,
            include_incidentals=True,
        )

        # Should have incidental reports
        assert len(result.incidental_reports) > 0

        # Should have citral in incidental totals
        # Lemongrass 85% citral max * 10% usage = 8.5%
        assert "5392-40-5" in result.incidental_totals
        assert result.incidental_totals["5392-40-5"] == pytest.approx(8.5, rel=0.01)
