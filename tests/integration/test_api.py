"""Integration tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_formula_payload():
    """Sample formula payload for API tests."""
    return {
        "name": "Test Fragrance",
        "ingredients": [
            {"cas_number": "64-17-5", "name": "Ethanol", "percentage": 70.0},
            {"cas_number": "78-70-6", "name": "Linalool", "percentage": 10.0},
            {"cas_number": "5989-27-5", "name": "d-Limonene", "percentage": 8.0},
            {"cas_number": "106-22-9", "name": "Citronellol", "percentage": 5.0},
            {"cas_number": "106-24-1", "name": "Geraniol", "percentage": 4.0},
            {"cas_number": "91-64-5", "name": "Coumarin", "percentage": 3.0},
        ],
    }


class TestHealthEndpoints:
    """Test health and info endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert data["name"] == "Smell-Reg API"

    def test_health_endpoint(self, client):
        """Test health endpoint returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestReferenceEndpoints:
    """Test reference data endpoints."""

    def test_get_markets(self, client):
        """Test getting list of markets."""
        response = client.get("/api/reference/markets")
        assert response.status_code == 200
        markets = response.json()
        assert isinstance(markets, list)
        assert len(markets) > 0
        # Check structure
        assert "value" in markets[0]
        assert "name" in markets[0]

    def test_get_product_types(self, client):
        """Test getting list of product types."""
        response = client.get("/api/reference/product-types")
        assert response.status_code == 200
        types = response.json()
        assert isinstance(types, list)
        assert len(types) > 0
        # Check for expected product type
        values = [t["value"] for t in types]
        assert "fine_fragrance" in values


class TestComplianceEndpoints:
    """Test compliance check endpoints."""

    def test_full_compliance_check(self, client, sample_formula_payload):
        """Test full compliance check endpoint."""
        request = {
            "formula": sample_formula_payload,
            "product_type": "fine_fragrance",
            "markets": ["us", "eu"],
            "fragrance_concentration": 20.0,
            "is_leave_on": True,
        }

        response = client.post("/api/compliance/check", json=request)
        assert response.status_code == 200
        data = response.json()
        assert "formula_name" in data
        assert "results" in data
        assert "is_compliant" in data

    def test_ifra_compliance_check(self, client, sample_formula_payload):
        """Test IFRA compliance endpoint."""
        request = {
            "formula": sample_formula_payload,
            "product_type": "fine_fragrance",
            "fragrance_concentration": 20.0,
        }

        response = client.post("/api/compliance/ifra", json=request)
        assert response.status_code == 200
        data = response.json()
        assert "is_compliant" in data
        assert "violations" in data
        assert "compliant_ingredients" in data

    def test_allergen_check(self, client, sample_formula_payload):
        """Test allergen check endpoint."""
        request = {
            "formula": sample_formula_payload,
            "markets": ["eu", "ca"],
            "fragrance_concentration": 20.0,
            "is_leave_on": True,
        }

        response = client.post("/api/compliance/allergens", json=request)
        assert response.status_code == 200
        data = response.json()
        assert "formula_name" in data
        assert "detected_allergens" in data
        assert "disclosure_required" in data

    def test_voc_check(self, client, sample_formula_payload):
        """Test VOC check endpoint."""
        request = {
            "formula": sample_formula_payload,
            "product_type": "fine_fragrance",
            "markets": ["us", "ca"],
        }

        response = client.post("/api/compliance/voc", json=request)
        assert response.status_code == 200
        data = response.json()
        assert "formula_name" in data
        assert "calculations" in data


class TestFormulaImport:
    """Test formula import endpoint."""

    def test_import_formula(self, client, sample_formula_payload):
        """Test importing a formula."""
        response = client.post("/api/formulas/import", json=sample_formula_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Fragrance"
        assert data["ingredient_count"] == 6
        assert data["total_percentage"] == 100.0


class TestValidation:
    """Test input validation."""

    def test_invalid_market(self, client, sample_formula_payload):
        """Test that invalid market returns error."""
        request = {
            "formula": sample_formula_payload,
            "product_type": "fine_fragrance",
            "markets": ["invalid_market"],
            "fragrance_concentration": 20.0,
        }

        response = client.post("/api/compliance/check", json=request)
        assert response.status_code == 400

    def test_invalid_product_type(self, client, sample_formula_payload):
        """Test that invalid product type returns error."""
        request = {
            "formula": sample_formula_payload,
            "product_type": "invalid_type",
            "markets": ["us"],
            "fragrance_concentration": 20.0,
        }

        response = client.post("/api/compliance/check", json=request)
        assert response.status_code == 400

    def test_invalid_concentration(self, client, sample_formula_payload):
        """Test that invalid concentration returns error."""
        request = {
            "formula": sample_formula_payload,
            "product_type": "fine_fragrance",
            "markets": ["us"],
            "fragrance_concentration": 150.0,  # Over 100%
        }

        response = client.post("/api/compliance/check", json=request)
        assert response.status_code == 422  # Validation error

    def test_missing_required_fields(self, client):
        """Test that missing required fields return error."""
        request = {
            "formula": {"name": "Test", "ingredients": []},
            # Missing product_type and markets
        }

        response = client.post("/api/compliance/check", json=request)
        assert response.status_code == 422
