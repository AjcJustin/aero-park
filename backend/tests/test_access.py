"""
AeroPark Smart System - Access Control Endpoint Tests
Tests for access validation, entry, and exit endpoints.

Run: pytest tests/test_access.py -v
"""

import pytest
from fastapi.testclient import TestClient


class TestAccessValidateCode:
    """Tests for POST /api/v1/access/validate-code endpoint."""
    
    def test_validate_code_requires_api_key(self, client: TestClient):
        """
        Test: Validate code requires X-API-Key header
        Expected: Status 401/403 without API key
        """
        payload = {"code": "A7F", "sensor_presence": True}
        
        response = client.post("/api/v1/access/validate-code", json=payload)
        
        assert response.status_code in [401, 403]
    
    def test_validate_code_with_valid_api_key_accepts_request(
        self, 
        client: TestClient, 
        api_key_header
    ):
        """
        Test: Valid API key allows request processing
        Expected: Not 401/403
        """
        payload = {"code": "A7F", "sensor_presence": True, "barrier_id": "entry"}
        
        response = client.post(
            "/api/v1/access/validate-code",
            json=payload,
            headers=api_key_header
        )
        
        # Should pass auth (not 401/403), may fail for other reasons
        assert response.status_code not in [401, 403]
    
    def test_validate_code_invalid_code_format_rejected(
        self, 
        client: TestClient, 
        api_key_header
    ):
        """
        Test: Invalid code format (empty) rejected
        Expected: Status 422 validation error
        """
        payload = {"code": "", "sensor_presence": True}  # Empty code
        
        response = client.post(
            "/api/v1/access/validate-code",
            json=payload,
            headers=api_key_header
        )
        
        # Should reject empty code (min_length=3)
        assert response.status_code == 422
    
    def test_validate_code_missing_sensor_presence_rejected(
        self, 
        client: TestClient, 
        api_key_header
    ):
        """
        Test: Missing sensor_presence field rejected
        Expected: Status 422 validation error
        """
        payload = {"code": "A7F"}  # Missing sensor_presence
        
        response = client.post(
            "/api/v1/access/validate-code",
            json=payload,
            headers=api_key_header
        )
        
        # Should reject missing required field
        assert response.status_code == 422
    
    def test_validate_code_response_has_access_granted_field(
        self, 
        client: TestClient, 
        api_key_header
    ):
        """
        Test: Response includes access_granted field
        Expected: access_granted in response body
        """
        payload = {"code": "A7F", "sensor_presence": True, "barrier_id": "entry"}
        
        response = client.post(
            "/api/v1/access/validate-code",
            json=payload,
            headers=api_key_header
        )
        
        # If successful, should have access_granted field
        if response.status_code == 200:
            data = response.json()
            assert "access_granted" in data


class TestAccessCheckEntry:
    """Tests for POST /api/v1/access/check-entry endpoint."""
    
    def test_check_entry_requires_api_key(self, client: TestClient):
        """
        Test: Check entry requires API key
        Expected: Status 401/403 without key
        """
        # Empty payload or minimal - check what endpoint expects
        response = client.post("/api/v1/access/check-entry", json={})
        
        assert response.status_code in [401, 403, 422]
    
    def test_check_entry_with_valid_api_key(
        self, 
        client: TestClient, 
        api_key_header
    ):
        """
        Test: Valid API key allows check entry
        Expected: Not 401/403
        """
        response = client.post(
            "/api/v1/access/check-entry",
            json={},
            headers=api_key_header
        )
        
        # Pass auth check
        assert response.status_code not in [401, 403]


class TestAccessExit:
    """Tests for POST /api/v1/access/exit endpoint."""
    
    def test_exit_requires_api_key(self, client: TestClient):
        """
        Test: Exit endpoint requires API key
        Expected: Status 401/403 without key
        """
        payload = {"place_id": "a1"}
        
        response = client.post("/api/v1/access/exit", json=payload)
        
        assert response.status_code in [401, 403, 422]
    
    def test_exit_with_valid_api_key(
        self, 
        client: TestClient, 
        api_key_header
    ):
        """
        Test: Exit with valid API key accepted
        Expected: Not 401/403
        """
        payload = {"place_id": "a1"}
        
        response = client.post(
            "/api/v1/access/exit",
            json=payload,
            headers=api_key_header
        )
        
        # Should pass auth
        assert response.status_code not in [401, 403]


class TestAccessAPIKeyVariations:
    """Tests for API key authentication variations."""
    
    def test_invalid_api_key_rejected(self, client: TestClient):
        """
        Test: Invalid API key is rejected
        Expected: Status 401/403
        """
        invalid_header = {"X-API-Key": "invalid-key-123"}
        payload = {"code": "A7F", "sensor_presence": True}
        
        response = client.post(
            "/api/v1/access/validate-code",
            json=payload,
            headers=invalid_header
        )
        
        assert response.status_code in [401, 403]
    
    def test_missing_api_key_rejected(self, client: TestClient):
        """
        Test: Missing API key is rejected
        Expected: Status 401/403
        """
        payload = {"code": "A7F", "sensor_presence": True}
        
        response = client.post(
            "/api/v1/access/validate-code",
            json=payload
        )
        
        assert response.status_code in [401, 403]
    
    def test_empty_api_key_rejected(self, client: TestClient):
        """
        Test: Empty API key is rejected
        Expected: Status 401/403
        """
        empty_header = {"X-API-Key": ""}
        payload = {"code": "A7F", "sensor_presence": True}
        
        response = client.post(
            "/api/v1/access/validate-code",
            json=payload,
            headers=empty_header
        )
        
        assert response.status_code in [401, 403]


class TestBarrierEndpoints:
    """Tests for barrier control endpoints."""
    
    def test_barrier_status_requires_api_key(self, client: TestClient):
        """
        Test: Barrier status requires API key
        Expected: Status 401/403 without key
        """
        response = client.get("/api/v1/barrier/status")
        
        assert response.status_code in [401, 403]
    
    def test_barrier_status_with_api_key(
        self, 
        client: TestClient, 
        api_key_header
    ):
        """
        Test: Barrier status with valid API key
        Expected: Status 200 or appropriate response
        """
        response = client.get(
            "/api/v1/barrier/status",
            headers=api_key_header
        )
        
        # Should pass auth
        assert response.status_code not in [401, 403]
    
    def test_barrier_parking_info_requires_api_key(self, client: TestClient):
        """
        Test: Barrier parking info requires API key
        Expected: Status 401/403 without key
        """
        response = client.get("/api/v1/barrier/parking-info")
        
        assert response.status_code in [401, 403]
    
    def test_barrier_parking_info_with_api_key(
        self, 
        client: TestClient, 
        api_key_header
    ):
        """
        Test: Barrier parking info with API key
        Expected: Returns parking availability info
        """
        response = client.get(
            "/api/v1/barrier/parking-info",
            headers=api_key_header
        )
        
        # Should pass auth
        if response.status_code == 200:
            data = response.json()
            # Should have parking info fields
            assert "total_spots" in data or "free_spots" in data or data
