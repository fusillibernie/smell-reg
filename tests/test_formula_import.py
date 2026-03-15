"""Tests for formula import from aroma-lab and regulatory info endpoints."""

import pytest
import respx
import httpx
from fastapi.testclient import TestClient

from api.main import app, formula_library


@pytest.fixture
def test_client():
    return TestClient(app)


class TestImportFromAromaLab:
    """Tests for POST /api/formulas/from-aroma-lab."""

    @respx.mock
    def test_import_formula_success(self, test_client):
        formula_data = {
            "id": "abc123",
            "name": "Rose Accord",
            "ingredients": [
                {"cas_number": "106-24-1", "name": "Geraniol", "percentage": 25.0},
                {"cas_number": "78-70-6", "name": "Linalool", "percentage": 15.0},
            ],
            "total_percentage": 40.0,
        }
        respx.get("http://localhost:8000/api/formulas/abc123").mock(
            return_value=httpx.Response(200, json=formula_data)
        )

        resp = test_client.post(
            "/api/formulas/from-aroma-lab",
            json={"formula_id": "abc123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Rose Accord"
        assert len(data["ingredients"]) == 2
        assert "imported" in data.get("tags", [])

        # Clean up
        if data.get("id"):
            formula_library.delete(data["id"])

    @respx.mock
    def test_import_formula_not_found(self, test_client):
        respx.get("http://localhost:8000/api/formulas/nonexistent").mock(
            return_value=httpx.Response(404)
        )

        resp = test_client.post(
            "/api/formulas/from-aroma-lab",
            json={"formula_id": "nonexistent"},
        )
        assert resp.status_code == 502

    @respx.mock
    def test_import_formula_service_unavailable(self, test_client):
        respx.get("http://localhost:8000/api/formulas/abc123").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        resp = test_client.post(
            "/api/formulas/from-aroma-lab",
            json={"formula_id": "abc123"},
        )
        assert resp.status_code == 502

    def test_import_rejects_invalid_formula_id(self, test_client):
        resp = test_client.post(
            "/api/formulas/from-aroma-lab",
            json={"formula_id": "../../etc/passwd"},
        )
        assert resp.status_code == 422  # Pydantic validation error


class TestListAromaLabFormulas:
    """Tests for GET /api/formulas/aroma-lab-list."""

    @respx.mock
    def test_list_success(self, test_client):
        respx.get("http://localhost:8000/api/formulas").mock(
            return_value=httpx.Response(200, json={
                "formulas": [
                    {"id": "f1", "name": "Rose Accord"},
                    {"id": "f2", "name": "Citrus"},
                ]
            })
        )

        resp = test_client.get("/api/formulas/aroma-lab-list")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["formulas"]) == 2

    @respx.mock
    def test_list_service_unavailable(self, test_client):
        respx.get("http://localhost:8000/api/formulas").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        resp = test_client.get("/api/formulas/aroma-lab-list")
        assert resp.status_code == 502


class TestIntegrationStatus:
    """Tests for GET /api/integration/status."""

    @respx.mock
    def test_status_connected(self, test_client):
        respx.get("http://localhost:8000/health").mock(
            return_value=httpx.Response(200, json={"status": "healthy"})
        )

        resp = test_client.get("/api/integration/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["aroma_lab"]["connected"] is True

    @respx.mock
    def test_status_disconnected(self, test_client):
        respx.get("http://localhost:8000/health").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        resp = test_client.get("/api/integration/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["aroma_lab"]["connected"] is False


class TestMaterialRegulatory:
    """Tests for GET /api/materials/{cas}/regulatory."""

    @respx.mock
    def test_regulatory_info(self, test_client):
        # Mock aroma-lab chemical fetch
        respx.get("http://localhost:8000/api/aromachemicals/78-70-6").mock(
            return_value=httpx.Response(200, json={
                "cas_number": "78-70-6",
                "name": "Linalool",
                "odor_description": "Floral, woody",
                "volatility": "heart",
            })
        )

        resp = test_client.get("/api/materials/78-70-6/regulatory")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cas_number"] == "78-70-6"
        # Should have chemical_properties from aroma-lab
        if data.get("chemical_properties"):
            assert data["chemical_properties"]["name"] == "Linalool"

    @respx.mock
    def test_regulatory_without_aroma_lab(self, test_client):
        respx.get("http://localhost:8000/api/aromachemicals/78-70-6").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        resp = test_client.get("/api/materials/78-70-6/regulatory")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cas_number"] == "78-70-6"
        assert data["chemical_properties"] is None

    def test_regulatory_rejects_invalid_cas(self, test_client):
        resp = test_client.get("/api/materials/../../etc/passwd/regulatory")
        # FastAPI normalizes paths, so traversal won't reach the endpoint
        assert resp.status_code in (400, 404, 422)

    def test_regulatory_rejects_traversal(self, test_client):
        resp = test_client.get("/api/materials/not-a-cas/regulatory")
        assert resp.status_code == 400
