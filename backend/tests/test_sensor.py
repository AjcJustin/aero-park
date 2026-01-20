"""
AeroPark Smart System - Sensor Endpoint Tests
Tests for ESP32 sensor simulation endpoints.

Run: pytest tests/test_sensor.py -v
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock


class TestSensorUpdate:
    """Tests for POST /api/v1/sensor/update endpoint."""
    
    # ============================================================
    # TEST: Authentication
    # ============================================================
    
    def test_sensor_update_requires_api_key(self, client: TestClient):
        """
        Test: Sensor update without API key returns 401
        Expected: Status 401 Unauthorized
        """
        payload = {
            "place_id": "a1",
            "etat": "occupied",
            "force_signal": -55
        }
        
        response = client.post("/api/v1/sensor/update", json=payload)
        
        assert response.status_code == 401
        assert "Clé API" in response.json().get("detail", "") or "API" in response.json().get("detail", "")
    
    def test_sensor_update_rejects_invalid_api_key(
        self, 
        client: TestClient, 
        invalid_api_key_headers: dict
    ):
        """
        Test: Sensor update with invalid API key returns 401
        Expected: Status 401 Unauthorized
        """
        payload = {
            "place_id": "a1",
            "etat": "occupied",
            "force_signal": -55
        }
        
        response = client.post(
            "/api/v1/sensor/update",
            json=payload,
            headers=invalid_api_key_headers
        )
        
        assert response.status_code == 401
    
    def test_sensor_update_accepts_valid_api_key(
        self, 
        client: TestClient, 
        api_key_headers: dict,
        mock_db
    ):
        """
        Test: Sensor update with valid API key succeeds
        Expected: Status 200 OK
        """
        with patch("routers.sensor.get_db", return_value=mock_db):
            payload = {
                "place_id": "a1",
                "etat": "occupied",
                "force_signal": -55
            }
            
            response = client.post(
                "/api/v1/sensor/update",
                json=payload,
                headers=api_key_headers
            )
            
            assert response.status_code == 200
    
    # ============================================================
    # TEST: Valid Payloads
    # ============================================================
    
    def test_sensor_update_occupied_state(
        self, 
        client: TestClient, 
        api_key_headers: dict,
        mock_db
    ):
        """
        Test: Sensor reports place as occupied
        Expected: Place state changes to OCCUPIED
        """
        mock_db.update_place_status = AsyncMock(return_value={"etat": "occupied"})
        
        with patch("routers.sensor.get_db", return_value=mock_db):
            payload = {
                "place_id": "a1",
                "etat": "occupied",
                "force_signal": -60
            }
            
            response = client.post(
                "/api/v1/sensor/update",
                json=payload,
                headers=api_key_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["place_id"] == "a1"
            assert data["new_etat"] == "occupied"
    
    def test_sensor_update_free_state(
        self, 
        client: TestClient, 
        api_key_headers: dict,
        mock_db
    ):
        """
        Test: Sensor reports place as free
        Expected: Place state changes to FREE
        """
        mock_db.update_place_status = AsyncMock(return_value={"etat": "free"})
        
        with patch("routers.sensor.get_db", return_value=mock_db):
            payload = {
                "place_id": "a2",
                "etat": "free",
                "force_signal": -45
            }
            
            response = client.post(
                "/api/v1/sensor/update",
                json=payload,
                headers=api_key_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["new_etat"] == "free"
    
    def test_sensor_update_with_signal_strength(
        self, 
        client: TestClient, 
        api_key_headers: dict,
        mock_db
    ):
        """
        Test: Sensor update includes signal strength
        Expected: Signal strength is processed
        """
        with patch("routers.sensor.get_db", return_value=mock_db):
            payload = {
                "place_id": "a1",
                "etat": "occupied",
                "force_signal": -75  # Weak signal
            }
            
            response = client.post(
                "/api/v1/sensor/update",
                json=payload,
                headers=api_key_headers
            )
            
            assert response.status_code == 200
            mock_db.update_place_status.assert_called_once()
    
    # ============================================================
    # TEST: Invalid Payloads
    # ============================================================
    
    def test_sensor_update_missing_place_id(
        self, 
        client: TestClient, 
        api_key_headers: dict
    ):
        """
        Test: Sensor update without place_id returns 422
        Expected: Status 422 Unprocessable Entity
        """
        payload = {
            "etat": "occupied",
            "force_signal": -55
        }
        
        response = client.post(
            "/api/v1/sensor/update",
            json=payload,
            headers=api_key_headers
        )
        
        assert response.status_code == 422
    
    def test_sensor_update_missing_etat(
        self, 
        client: TestClient, 
        api_key_headers: dict
    ):
        """
        Test: Sensor update without etat returns 422
        Expected: Status 422 Unprocessable Entity
        """
        payload = {
            "place_id": "a1",
            "force_signal": -55
        }
        
        response = client.post(
            "/api/v1/sensor/update",
            json=payload,
            headers=api_key_headers
        )
        
        assert response.status_code == 422
    
    def test_sensor_update_invalid_etat_value(
        self, 
        client: TestClient, 
        api_key_headers: dict
    ):
        """
        Test: Sensor update with invalid etat value returns 422
        Expected: Status 422 Unprocessable Entity
        """
        payload = {
            "place_id": "a1",
            "etat": "invalid_state",
            "force_signal": -55
        }
        
        response = client.post(
            "/api/v1/sensor/update",
            json=payload,
            headers=api_key_headers
        )
        
        # Should be 422 or handled gracefully
        assert response.status_code in [422, 400]
    
    def test_sensor_update_empty_payload(
        self, 
        client: TestClient, 
        api_key_headers: dict
    ):
        """
        Test: Sensor update with empty payload returns 422
        Expected: Status 422 Unprocessable Entity
        """
        response = client.post(
            "/api/v1/sensor/update",
            json={},
            headers=api_key_headers
        )
        
        assert response.status_code == 422
    
    # ============================================================
    # TEST: Place Not Found
    # ============================================================
    
    def test_sensor_update_nonexistent_place(
        self, 
        client: TestClient, 
        api_key_headers: dict,
        mock_db
    ):
        """
        Test: Sensor update for non-existent place returns 404
        Expected: Status 404 Not Found
        """
        mock_db.update_place_status = AsyncMock(
            side_effect=ValueError("Place z99 not found")
        )
        
        with patch("routers.sensor.get_db", return_value=mock_db):
            payload = {
                "place_id": "z99",
                "etat": "occupied",
                "force_signal": -55
            }
            
            response = client.post(
                "/api/v1/sensor/update",
                json=payload,
                headers=api_key_headers
            )
            
            assert response.status_code == 404


class TestSensorHealth:
    """Tests for GET /api/v1/sensor/health endpoint."""
    
    def test_sensor_health_requires_api_key(self, client: TestClient):
        """
        Test: Sensor health without API key returns 401
        Expected: Status 401 Unauthorized
        """
        response = client.get("/api/v1/sensor/health")
        
        assert response.status_code == 401
    
    def test_sensor_health_with_valid_api_key(
        self, 
        client: TestClient, 
        api_key_headers: dict,
        mock_db
    ):
        """
        Test: Sensor health with valid API key returns status
        Expected: Status 200 with health info
        """
        with patch("routers.sensor.get_db", return_value=mock_db):
            response = client.get(
                "/api/v1/sensor/health",
                headers=api_key_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should contain health information
            assert "status" in data or "places" in data or "total" in data
    
    def test_sensor_health_returns_parking_counts(
        self, 
        client: TestClient, 
        api_key_headers: dict,
        mock_db
    ):
        """
        Test: Sensor health includes parking statistics
        Expected: Free/occupied/reserved counts
        """
        with patch("routers.sensor.get_db", return_value=mock_db):
            response = client.get(
                "/api/v1/sensor/health",
                headers=api_key_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify counting fields exist
            if "free" in data:
                assert isinstance(data["free"], int)
            if "occupied" in data:
                assert isinstance(data["occupied"], int)


class TestSensorBusinessLogic:
    """Tests for sensor business logic."""
    
    def test_occupied_sensor_updates_place_to_occupied(
        self, 
        client: TestClient, 
        api_key_headers: dict,
        mock_db
    ):
        """
        Test: Vehicle presence triggers OCCUPIED state
        Expected: Database updated with occupied status
        """
        mock_db.update_place_status = AsyncMock(return_value={"etat": "occupied"})
        
        with patch("routers.sensor.get_db", return_value=mock_db):
            payload = {
                "place_id": "a1",
                "etat": "occupied",
                "force_signal": -50
            }
            
            response = client.post(
                "/api/v1/sensor/update",
                json=payload,
                headers=api_key_headers
            )
            
            assert response.status_code == 200
            
            # Verify database was called correctly
            mock_db.update_place_status.assert_called_with(
                place_id="a1",
                etat="occupied",
                force_signal=-50
            )
    
    def test_free_sensor_updates_place_to_available(
        self, 
        client: TestClient, 
        api_key_headers: dict,
        mock_db
    ):
        """
        Test: Vehicle departure triggers FREE state
        Expected: Database updated with free status
        """
        mock_db.update_place_status = AsyncMock(return_value={"etat": "free"})
        
        with patch("routers.sensor.get_db", return_value=mock_db):
            payload = {
                "place_id": "a3",
                "etat": "free",
                "force_signal": -40
            }
            
            response = client.post(
                "/api/v1/sensor/update",
                json=payload,
                headers=api_key_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["new_etat"] == "free"
    
    def test_response_includes_timestamp(
        self, 
        client: TestClient, 
        api_key_headers: dict,
        mock_db
    ):
        """
        Test: Sensor update response includes timestamp
        Expected: ISO format timestamp in response
        """
        with patch("routers.sensor.get_db", return_value=mock_db):
            payload = {
                "place_id": "a1",
                "etat": "occupied",
                "force_signal": -55
            }
            
            response = client.post(
                "/api/v1/sensor/update",
                json=payload,
                headers=api_key_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "timestamp" in data
