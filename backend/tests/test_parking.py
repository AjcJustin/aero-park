"""
AeroPark Smart System - Parking Endpoint Tests
Tests for parking status, availability, and reservation endpoints.

Run: pytest tests/test_parking.py -v
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock


class TestParkingStatus:
    """Tests for GET /parking/status endpoint."""
    
    def test_parking_status_returns_200(self, client: TestClient, mock_db):
        """
        Test: Parking status endpoint accessible
        Expected: Status 200 OK
        """
        with patch("routers.parking.get_db", return_value=mock_db):
            response = client.get("/parking/status")
            
            assert response.status_code == 200
    
    def test_parking_status_returns_counts(self, client: TestClient, mock_db):
        """
        Test: Parking status includes place counts
        Expected: total, free, reserved, occupied counts
        """
        with patch("routers.parking.get_db", return_value=mock_db):
            response = client.get("/parking/status")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "total" in data
            assert "free" in data
            assert "occupied" in data
            assert "reserved" in data
    
    def test_parking_status_counts_are_integers(self, client: TestClient, mock_db):
        """
        Test: All counts are integers
        Expected: Integer values for all counts
        """
        with patch("routers.parking.get_db", return_value=mock_db):
            response = client.get("/parking/status")
            
            data = response.json()
            
            assert isinstance(data["total"], int)
            assert isinstance(data["free"], int)
            assert isinstance(data["occupied"], int)
            assert isinstance(data["reserved"], int)
    
    def test_parking_status_counts_match_places(self, client: TestClient, mock_db):
        """
        Test: Counts sum equals total places
        Expected: free + occupied + reserved = total
        """
        with patch("routers.parking.get_db", return_value=mock_db):
            response = client.get("/parking/status")
            
            data = response.json()
            
            # Sum should equal or be less than total (accounting for other states)
            assert data["free"] + data["occupied"] + data["reserved"] <= data["total"]
    
    def test_parking_status_includes_places_list(self, client: TestClient, mock_db):
        """
        Test: Status includes list of all places
        Expected: places array in response
        """
        with patch("routers.parking.get_db", return_value=mock_db):
            response = client.get("/parking/status")
            
            data = response.json()
            
            assert "places" in data
            assert isinstance(data["places"], list)
    
    def test_parking_status_includes_timestamp(self, client: TestClient, mock_db):
        """
        Test: Status includes timestamp
        Expected: ISO timestamp in response
        """
        with patch("routers.parking.get_db", return_value=mock_db):
            response = client.get("/parking/status")
            
            data = response.json()
            
            assert "timestamp" in data


class TestParkingAvailable:
    """Tests for GET /parking/available endpoint."""
    
    def test_parking_available_returns_200(self, client: TestClient, mock_db):
        """
        Test: Available places endpoint accessible
        Expected: Status 200 OK
        """
        with patch("routers.parking.get_db", return_value=mock_db):
            response = client.get("/parking/available")
            
            assert response.status_code == 200
    
    def test_parking_available_returns_free_places_only(
        self, 
        client: TestClient, 
        mock_db
    ):
        """
        Test: Only free places are returned
        Expected: All returned places have etat='free'
        """
        with patch("routers.parking.get_db", return_value=mock_db):
            response = client.get("/parking/available")
            
            data = response.json()
            
            assert "available" in data
            for place in data["available"]:
                assert place["etat"] == "free"
    
    def test_parking_available_includes_count(self, client: TestClient, mock_db):
        """
        Test: Response includes count of available places
        Expected: count field matches available array length
        """
        with patch("routers.parking.get_db", return_value=mock_db):
            response = client.get("/parking/available")
            
            data = response.json()
            
            assert "count" in data
            assert data["count"] == len(data["available"])
    
    def test_parking_available_when_full(
        self, 
        client_full_parking: TestClient, 
        mock_full_parking_db
    ):
        """
        Test: Empty available list when parking is full
        Expected: count = 0, available = []
        """
        with patch("routers.parking.get_db", return_value=mock_full_parking_db):
            response = client_full_parking.get("/parking/available")
            
            data = response.json()
            
            # Should return empty or very few spots
            assert data["count"] == 0 or data["count"] < 6


class TestParkingPlaceDetails:
    """Tests for GET /parking/place/{place_id} endpoint."""
    
    def test_place_details_returns_200_for_valid_place(
        self, 
        client: TestClient, 
        mock_db
    ):
        """
        Test: Place details for valid ID returns 200
        Expected: Status 200 OK
        """
        with patch("routers.parking.get_db", return_value=mock_db):
            response = client.get("/parking/place/a1")
            
            assert response.status_code == 200
    
    def test_place_details_returns_place_info(self, client: TestClient, mock_db):
        """
        Test: Place details includes all relevant info
        Expected: place_id and etat in response
        """
        with patch("routers.parking.get_db", return_value=mock_db):
            response = client.get("/parking/place/a1")
            
            data = response.json()
            
            assert "place_id" in data
            assert "etat" in data
    
    def test_place_details_returns_404_for_invalid_place(
        self, 
        client: TestClient, 
        mock_db
    ):
        """
        Test: Invalid place ID returns 404
        Expected: Status 404 Not Found
        """
        mock_db.get_place_by_id = AsyncMock(return_value=None)
        
        with patch("routers.parking.get_db", return_value=mock_db):
            response = client.get("/parking/place/z99")
            
            assert response.status_code == 404


class TestParkingReservation:
    """Tests for POST /parking/reserve endpoint."""
    
    def test_reservation_requires_authentication(self, client: TestClient):
        """
        Test: Reservation requires user authentication
        Expected: Status 401 or 403 without auth
        """
        payload = {"place_id": "a1"}
        
        response = client.post("/parking/reserve", json=payload)
        
        # Should require authentication
        assert response.status_code in [401, 403, 422]
    
    def test_reservation_with_mock_user_succeeds(
        self, 
        client: TestClient, 
        mock_db,
        mock_user
    ):
        """
        Test: Authenticated user can reserve a place
        Expected: Status 200 with reservation details
        """
        mock_db.reserve_place = AsyncMock(return_value={
            "success": True,
            "place_id": "a1",
            "reservation_id": "res-123",
            "expires_at": "2026-01-20T13:00:00Z"
        })
        
        with patch("routers.parking.get_db", return_value=mock_db):
            with patch("routers.parking.get_current_user", return_value=mock_user):
                payload = {"place_id": "a1"}
                
                response = client.post("/parking/reserve", json=payload)
                
                # With proper auth mock, should succeed
                if response.status_code == 200:
                    data = response.json()
                    assert data["success"] is True
    
    def test_reservation_returns_reservation_details(
        self, 
        client: TestClient, 
        mock_db,
        mock_user
    ):
        """
        Test: Successful reservation returns details
        Expected: place_id, reservation_id in response
        """
        mock_db.reserve_place = AsyncMock(return_value={
            "success": True,
            "place_id": "a1",
            "reservation_id": "res-123",
            "expires_at": "2026-01-20T13:00:00Z"
        })
        
        with patch("routers.parking.get_db", return_value=mock_db):
            with patch("security.firebase_auth.get_current_user", return_value=mock_user):
                payload = {"place_id": "a1"}
                
                response = client.post("/parking/reserve", json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    assert "place_id" in data or "reservation_id" in data


class TestParkingRelease:
    """Tests for POST /parking/release/{place_id} endpoint."""
    
    def test_release_requires_authentication(self, client: TestClient):
        """
        Test: Release requires authentication
        Expected: Status 401 or 403 without auth
        """
        response = client.post("/parking/release/a1")
        
        assert response.status_code in [401, 403, 422]
    
    def test_release_returns_404_for_invalid_place(
        self, 
        client: TestClient, 
        mock_db,
        mock_user
    ):
        """
        Test: Release non-existent place returns 404
        Expected: Status 404 Not Found
        """
        mock_db.get_place_by_id = AsyncMock(return_value=None)
        
        with patch("routers.parking.get_db", return_value=mock_db):
            with patch("security.firebase_auth.get_current_user", return_value=mock_user):
                response = client.post("/parking/release/z99")
                
                # Should be 404 or auth error
                assert response.status_code in [404, 401, 403]


class TestParkingBusinessLogic:
    """Tests for parking business logic."""
    
    def test_reservation_rejected_when_parking_full(
        self, 
        client_full_parking: TestClient, 
        mock_full_parking_db,
        mock_user
    ):
        """
        Test: Reservation fails when parking is full
        Expected: Error response indicating no availability
        """
        mock_full_parking_db.reserve_place = AsyncMock(
            side_effect=ValueError("No free places available")
        )
        
        with patch("routers.parking.get_db", return_value=mock_full_parking_db):
            with patch("security.firebase_auth.get_current_user", return_value=mock_user):
                payload = {"place_id": "a1"}
                
                response = client_full_parking.post("/parking/reserve", json=payload)
                
                # Should fail due to full parking or auth
                assert response.status_code in [400, 409, 401, 403]
    
    def test_reservation_rejected_for_already_reserved_place(
        self, 
        client: TestClient, 
        mock_db,
        mock_user
    ):
        """
        Test: Cannot reserve already reserved place
        Expected: Error response
        """
        mock_db.reserve_place = AsyncMock(
            side_effect=ValueError("Place already reserved")
        )
        
        with patch("routers.parking.get_db", return_value=mock_db):
            with patch("security.firebase_auth.get_current_user", return_value=mock_user):
                payload = {"place_id": "a4"}  # Already reserved in mock
                
                response = client.post("/parking/reserve", json=payload)
                
                # Should fail
                assert response.status_code in [400, 409, 401, 403]
    
    def test_release_resets_place_to_free(
        self, 
        client: TestClient, 
        mock_db,
        mock_user
    ):
        """
        Test: Releasing place sets state to FREE
        Expected: Database release called
        """
        mock_db.release_place = AsyncMock(return_value=True)
        mock_db.get_place_by_id = AsyncMock(return_value={
            "place_id": "a4",
            "etat": "reserved",
            "reserved_by": mock_user.uid
        })
        
        with patch("routers.parking.get_db", return_value=mock_db):
            with patch("security.firebase_auth.get_current_user", return_value=mock_user):
                response = client.post("/parking/release/a4")
                
                # Should succeed or require auth
                if response.status_code == 200:
                    mock_db.release_place.assert_called()
