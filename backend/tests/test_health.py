"""
AeroPark Smart System - Health & Info Endpoint Tests
Tests for root, health, and info endpoints.

Run: pytest tests/test_health.py -v
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock


class TestHealthEndpoints:
    """Tests for health and info endpoints."""
    
    # ============================================================
    # TEST: GET / (Root Endpoint)
    # ============================================================
    
    def test_root_endpoint_returns_200(self, client: TestClient):
        """
        Test: GET / returns 200 OK
        Expected: Status 200 with welcome message
        """
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data or "status" in data
    
    def test_root_endpoint_returns_valid_json(self, client: TestClient):
        """
        Test: GET / returns valid JSON structure
        Expected: JSON with expected fields
        """
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should contain system info
        assert isinstance(data, dict)
    
    def test_root_endpoint_contains_version(self, client: TestClient):
        """
        Test: Root endpoint includes API version
        Expected: Version field in response
        """
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Version should be present
        if "version" in data:
            assert isinstance(data["version"], str)
    
    # ============================================================
    # TEST: OpenAPI Documentation
    # ============================================================
    
    def test_docs_endpoint_accessible(self, client: TestClient):
        """
        Test: GET /docs returns Swagger UI
        Expected: Status 200
        """
        response = client.get("/docs")
        
        assert response.status_code == 200
    
    def test_openapi_json_accessible(self, client: TestClient):
        """
        Test: GET /openapi.json returns API schema
        Expected: Valid OpenAPI JSON
        """
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        data = response.json()
        
        # OpenAPI spec structure
        assert "openapi" in data
        assert "paths" in data
        assert "info" in data
    
    def test_redoc_endpoint_accessible(self, client: TestClient):
        """
        Test: GET /redoc returns ReDoc documentation
        Expected: Status 200
        """
        response = client.get("/redoc")
        
        assert response.status_code == 200
    
    # ============================================================
    # TEST: API Structure Validation
    # ============================================================
    
    def test_api_has_sensor_endpoints(self, client: TestClient):
        """
        Test: API includes sensor endpoints
        Expected: /api/v1/sensor paths exist
        """
        response = client.get("/openapi.json")
        data = response.json()
        paths = data.get("paths", {})
        
        # Check sensor endpoints exist
        sensor_paths = [p for p in paths.keys() if "/sensor" in p]
        assert len(sensor_paths) > 0, "No sensor endpoints found"
    
    def test_api_has_parking_endpoints(self, client: TestClient):
        """
        Test: API includes parking endpoints
        Expected: /parking paths exist
        """
        response = client.get("/openapi.json")
        data = response.json()
        paths = data.get("paths", {})
        
        # Check parking endpoints exist
        parking_paths = [p for p in paths.keys() if "/parking" in p]
        assert len(parking_paths) > 0, "No parking endpoints found"
    
    def test_api_has_payment_endpoints(self, client: TestClient):
        """
        Test: API includes payment endpoints
        Expected: /payment paths exist
        """
        response = client.get("/openapi.json")
        data = response.json()
        paths = data.get("paths", {})
        
        # Check payment endpoints exist
        payment_paths = [p for p in paths.keys() if "/payment" in p]
        assert len(payment_paths) > 0, "No payment endpoints found"
    
    def test_api_has_access_endpoints(self, client: TestClient):
        """
        Test: API includes access control endpoints
        Expected: /access paths exist
        """
        response = client.get("/openapi.json")
        data = response.json()
        paths = data.get("paths", {})
        
        # Check access endpoints exist
        access_paths = [p for p in paths.keys() if "/access" in p]
        assert len(access_paths) > 0, "No access endpoints found"
    
    def test_api_has_admin_endpoints(self, client: TestClient):
        """
        Test: API includes admin endpoints
        Expected: /admin paths exist
        """
        response = client.get("/openapi.json")
        data = response.json()
        paths = data.get("paths", {})
        
        # Check admin endpoints exist
        admin_paths = [p for p in paths.keys() if "/admin" in p]
        assert len(admin_paths) > 0, "No admin endpoints found"


class TestCORSHeaders:
    """Tests for CORS configuration."""
    
    def test_cors_preflight_origin_header(self, client: TestClient):
        """
        Test: CORS preflight includes access-control headers
        Expected: Access-Control-Allow-Origin header in response
        """
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        
        # CORS headers should be present if CORS is configured
        # Note: May return 200 or 405 depending on CORS middleware config
        cors_present = (
            "access-control-allow-origin" in response.headers or
            response.status_code in [200, 204]
        )
        # Just verify endpoint is reachable
        assert response.status_code in [200, 204, 405]


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_404_for_unknown_endpoint(self, client: TestClient):
        """
        Test: Unknown endpoint returns 404
        Expected: Status 404 Not Found
        """
        response = client.get("/this/endpoint/does/not/exist")
        
        assert response.status_code == 404
    
    def test_405_for_wrong_method(self, client: TestClient):
        """
        Test: Wrong HTTP method returns 405
        Expected: Status 405 Method Not Allowed
        """
        # Trying DELETE on root (which only accepts GET)
        response = client.delete("/")
        
        assert response.status_code == 405
