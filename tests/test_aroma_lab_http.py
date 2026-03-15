"""Tests for the AromaLabHTTPClient HTTP integration."""

import pytest
import respx
import httpx

from src.integrations.aroma_lab import (
    AromaLabHTTPClient,
    IFRADatabase,
    IFRARestriction,
    FormulaData,
)


@pytest.fixture
def client():
    """Create an AromaLabHTTPClient with a test base URL."""
    return AromaLabHTTPClient(base_url="http://testserver:8000")


@pytest.mark.asyncio
class TestAromaLabHTTPClientHealth:
    """Tests for health check."""

    @respx.mock
    async def test_health_check_success(self, client):
        respx.get("http://testserver:8000/health").mock(
            return_value=httpx.Response(200, json={"status": "healthy"})
        )
        assert await client.check_health() is True

    @respx.mock
    async def test_health_check_failure(self, client):
        respx.get("http://testserver:8000/health").mock(
            return_value=httpx.Response(500)
        )
        assert await client.check_health() is False

    @respx.mock
    async def test_health_check_connection_error(self, client):
        respx.get("http://testserver:8000/health").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        assert await client.check_health() is False


@pytest.mark.asyncio
class TestAromaLabHTTPClientIFRA:
    """Tests for IFRA restriction fetching."""

    @respx.mock
    async def test_fetch_ifra_restrictions_success(self, client):
        ifra_data = {
            "metadata": {"amendment": 51},
            "restrictions": [
                {
                    "cas_number": "8007-00-9",
                    "name": "Peru Balsam crude",
                    "restriction_type": "prohibition",
                    "category_limits": {},
                    "general_limit": 0.0,
                    "amendment_number": 51,
                },
                {
                    "cas_number": "97-53-0",
                    "name": "Eugenol",
                    "restriction_type": "sensitization",
                    "category_limits": {"1": 0.5, "4": 2.0},
                    "general_limit": None,
                    "amendment_number": 51,
                },
            ],
        }
        respx.get("http://testserver:8000/api/ifra-restrictions").mock(
            return_value=httpx.Response(200, json=ifra_data)
        )

        restrictions = await client.fetch_ifra_restrictions()
        assert restrictions is not None
        assert len(restrictions) == 2
        assert isinstance(restrictions[0], IFRARestriction)
        assert restrictions[0].cas_number == "8007-00-9"
        assert restrictions[1].name == "Eugenol"

    @respx.mock
    async def test_fetch_ifra_restrictions_connection_error(self, client):
        respx.get("http://testserver:8000/api/ifra-restrictions").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        restrictions = await client.fetch_ifra_restrictions()
        assert restrictions is None


@pytest.mark.asyncio
class TestAromaLabHTTPClientFormula:
    """Tests for formula fetching."""

    @respx.mock
    async def test_fetch_formula_success(self, client):
        formula_data = {
            "id": "abc123",
            "name": "Rose Accord",
            "ingredients": [
                {"cas_number": "106-24-1", "name": "Geraniol", "percentage": 25.0},
                {"cas_number": "78-70-6", "name": "Linalool", "percentage": 15.0},
            ],
            "total_percentage": 40.0,
        }
        respx.get("http://testserver:8000/api/formulas/abc123").mock(
            return_value=httpx.Response(200, json=formula_data)
        )

        formula = await client.fetch_formula("abc123")
        assert formula is not None
        assert isinstance(formula, FormulaData)
        assert formula.name == "Rose Accord"
        assert len(formula.ingredients) == 2
        assert formula.ingredients[0].cas_number == "106-24-1"

    @respx.mock
    async def test_fetch_formula_not_found(self, client):
        respx.get("http://testserver:8000/api/formulas/nonexistent").mock(
            return_value=httpx.Response(404)
        )

        formula = await client.fetch_formula("nonexistent")
        assert formula is None

    @respx.mock
    async def test_fetch_formula_connection_error(self, client):
        respx.get("http://testserver:8000/api/formulas/abc123").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        formula = await client.fetch_formula("abc123")
        assert formula is None


@pytest.mark.asyncio
class TestAromaLabHTTPClientChemical:
    """Tests for aromachemical fetching."""

    @respx.mock
    async def test_fetch_aromachemical_success(self, client):
        chem_data = {
            "cas_number": "78-70-6",
            "name": "Linalool",
            "odor_description": "Floral, woody",
            "volatility": "heart",
            "odor_families": ["floral", "woody"],
        }
        respx.get("http://testserver:8000/api/aromachemicals/78-70-6").mock(
            return_value=httpx.Response(200, json=chem_data)
        )

        result = await client.fetch_aromachemical("78-70-6")
        assert result is not None
        assert result["name"] == "Linalool"

    @respx.mock
    async def test_fetch_aromachemical_not_found(self, client):
        respx.get("http://testserver:8000/api/aromachemicals/999-99-9").mock(
            return_value=httpx.Response(404)
        )

        result = await client.fetch_aromachemical("999-99-9")
        assert result is None


@pytest.mark.asyncio
class TestAromaLabHTTPClientFormulas:
    """Tests for listing formulas."""

    @respx.mock
    async def test_list_formulas_success(self, client):
        formulas = {
            "formulas": [
                {"id": "f1", "name": "Rose Accord"},
                {"id": "f2", "name": "Citrus Splash"},
            ]
        }
        respx.get("http://testserver:8000/api/formulas").mock(
            return_value=httpx.Response(200, json=formulas)
        )

        result = await client.list_formulas()
        assert result is not None
        assert len(result) == 2

    @respx.mock
    async def test_list_formulas_connection_error(self, client):
        respx.get("http://testserver:8000/api/formulas").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        result = await client.list_formulas()
        assert result is None


@pytest.mark.asyncio
class TestIFRADatabaseAsyncLoad:
    """Tests for IFRADatabase async loading with HTTP fallback."""

    @respx.mock
    async def test_load_async_from_http(self):
        """When HTTP succeeds, should load from API."""
        ifra_data = {
            "restrictions": [
                {
                    "cas_number": "97-53-0",
                    "name": "Eugenol",
                    "restriction_type": "sensitization",
                    "category_limits": {"4": 2.0},
                    "general_limit": None,
                },
            ],
        }
        respx.get("http://localhost:8000/api/ifra-restrictions").mock(
            return_value=httpx.Response(200, json=ifra_data)
        )

        db = IFRADatabase(data_path=None)
        db._loaded = False
        await db.load_async()

        assert db._loaded is True
        restriction = db.get_by_cas("97-53-0")
        assert restriction is not None
        assert restriction.name == "Eugenol"

    @respx.mock
    async def test_load_async_falls_back_to_file(self, tmp_path):
        """When HTTP fails, should fall back to file."""
        respx.get("http://localhost:8000/api/ifra-restrictions").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        # Create a test IFRA file
        ifra_file = tmp_path / "ifra_restrictions.json"
        ifra_file.write_text(
            '{"restrictions": [{"cas_number": "8007-00-9", "name": "Peru Balsam",'
            '"restriction_type": "prohibition", "category_limits": {}, "general_limit": 0.0}]}'
        )

        db = IFRADatabase(data_path=ifra_file)
        await db.load_async()

        assert db._loaded is True
        restriction = db.get_by_cas("8007-00-9")
        assert restriction is not None
        assert restriction.name == "Peru Balsam"
