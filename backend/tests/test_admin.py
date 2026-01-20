"""
AeroPark Smart System - Admin Endpoint Tests
Tests for admin-only parking management and statistics endpoints.

Run: pytest tests/test_admin.py -v
"""

import pytest
from fastapi.testclient import TestClient


class TestAdminAuthentication:
    """Tests for admin authentication requirements."""
    
    def test_admin_parking_all_requires_auth(self, client: TestClient):
        """
        Test: Admin parking all requires authentication
        Expected: Status 401/403 without auth
        """
        response = client.get("/admin/parking/all")
        
        assert response.status_code in [401, 403]
    
    def test_admin_stats_requires_auth(self, client: TestClient):
        """
        Test: Admin stats requires authentication
        Expected: Status 401/403 without auth
        """
        response = client.get("/admin/parking/stats")
        
        assert response.status_code in [401, 403]
    
    def test_admin_force_release_requires_auth(self, client: TestClient):
        """
        Test: Admin force release requires authentication
        Expected: Status 401/403 without auth
        """
        response = client.post("/admin/parking/force-release/a1")
        
        assert response.status_code in [401, 403]
    
    def test_admin_reservations_requires_auth(self, client: TestClient):
        """
        Test: Admin reservations requires authentication
        Expected: Status 401/403 without auth
        """
        response = client.get("/admin/parking/reservations")
        
        assert response.status_code in [401, 403]
    
    def test_admin_payments_requires_auth(self, client: TestClient):
        """
        Test: Admin payments requires authentication
        Expected: Status 401/403 without auth
        """
        response = client.get("/admin/parking/payments")
        
        assert response.status_code in [401, 403]
    
    def test_admin_barrier_logs_requires_auth(self, client: TestClient):
        """
        Test: Admin barrier logs requires authentication
        Expected: Status 401/403 without auth
        """
        response = client.get("/admin/parking/barrier-logs")
        
        assert response.status_code in [401, 403]
    
    def test_admin_system_status_requires_auth(self, client: TestClient):
        """
        Test: Admin system status requires authentication
        Expected: Status 401/403 without auth
        """
        response = client.get("/admin/parking/system-status")
        
        assert response.status_code in [401, 403]
    
    def test_admin_access_codes_requires_auth(self, client: TestClient):
        """
        Test: Admin access codes requires authentication
        Expected: Status 401/403 without auth
        """
        response = client.get("/admin/parking/access-codes")
        
        assert response.status_code in [401, 403]
    
    def test_admin_initialize_requires_auth(self, client: TestClient):
        """
        Test: Admin initialize requires authentication
        Expected: Status 401/403 without auth
        """
        response = client.post("/admin/parking/initialize")
        
        assert response.status_code in [401, 403]


class TestAdminEndpointsExist:
    """Tests that admin endpoints are properly registered."""
    
    def test_admin_parking_all_endpoint_exists(self, client: TestClient):
        """
        Test: Admin parking all endpoint is registered
        Expected: Not 404
        """
        response = client.get("/admin/parking/all")
        
        # Should exist (auth error, not 404)
        assert response.status_code != 404
    
    def test_admin_stats_endpoint_exists(self, client: TestClient):
        """
        Test: Admin stats endpoint is registered
        Expected: Not 404
        """
        response = client.get("/admin/parking/stats")
        
        assert response.status_code != 404
    
    def test_admin_reservations_endpoint_exists(self, client: TestClient):
        """
        Test: Admin reservations endpoint is registered
        Expected: Not 404
        """
        response = client.get("/admin/parking/reservations")
        
        assert response.status_code != 404
    
    def test_admin_payments_endpoint_exists(self, client: TestClient):
        """
        Test: Admin payments endpoint is registered
        Expected: Not 404
        """
        response = client.get("/admin/parking/payments")
        
        assert response.status_code != 404
    
    def test_admin_force_release_endpoint_exists(self, client: TestClient):
        """
        Test: Admin force release endpoint is registered
        Expected: Not 404
        """
        response = client.post("/admin/parking/force-release/test-place")
        
        assert response.status_code != 404
    
    def test_admin_cancel_reservation_endpoint_exists(self, client: TestClient):
        """
        Test: Admin cancel reservation endpoint is registered
        Expected: Not 404
        """
        response = client.post("/admin/parking/reservations/cancel/test-res")
        
        assert response.status_code != 404
    
    def test_admin_refund_endpoint_exists(self, client: TestClient):
        """
        Test: Admin refund endpoint is registered
        Expected: Not 404
        """
        response = client.post("/admin/parking/payments/refund/test-pay")
        
        assert response.status_code != 404
    
    def test_admin_invalidate_code_endpoint_exists(self, client: TestClient):
        """
        Test: Admin invalidate code endpoint is registered
        Expected: Not 404
        """
        response = client.post("/admin/parking/access-codes/invalidate/ABC")
        
        assert response.status_code != 404


class TestAdminMethodValidation:
    """Tests for correct HTTP methods on admin endpoints."""
    
    def test_admin_parking_all_is_get(self, client: TestClient):
        """
        Test: Admin parking all uses GET method
        Expected: POST returns 405
        """
        response = client.post("/admin/parking/all")
        
        assert response.status_code == 405
    
    def test_admin_stats_is_get(self, client: TestClient):
        """
        Test: Admin stats uses GET method
        Expected: POST returns 405
        """
        response = client.post("/admin/parking/stats")
        
        assert response.status_code == 405
    
    def test_admin_force_release_is_post(self, client: TestClient):
        """
        Test: Admin force release uses POST method
        Expected: GET returns 405
        """
        response = client.get("/admin/parking/force-release/a1")
        
        assert response.status_code == 405
    
    def test_admin_initialize_is_post(self, client: TestClient):
        """
        Test: Admin initialize uses POST method
        Expected: GET returns 405
        """
        response = client.get("/admin/parking/initialize")
        
        assert response.status_code == 405
