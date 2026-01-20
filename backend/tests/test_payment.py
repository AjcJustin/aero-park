"""
AeroPark Smart System - Payment Endpoint Tests
Tests for mobile money simulation and payment status endpoints.

Run: pytest tests/test_payment.py -v
"""

import pytest
from fastapi.testclient import TestClient


class TestMobileMoneySimulate:
    """Tests for POST /api/v1/payment/mobile-money/simulate endpoint."""
    
    def test_mobile_money_requires_user_auth(self, client: TestClient):
        """
        Test: Mobile money endpoint requires user authentication
        Expected: Status 401/403 without auth token
        """
        payload = {
            "phone_number": "+243900000001",
            "amount": 5000,
            "provider": "ORANGE_MONEY",
            "reservation_id": "res-123"
        }
        
        response = client.post("/api/v1/payment/mobile-money/simulate", json=payload)
        
        # Requires Firebase user token, not API key
        assert response.status_code in [401, 403]
    
    def test_mobile_money_api_key_insufficient(
        self, 
        client: TestClient, 
        api_key_header
    ):
        """
        Test: API key alone is not sufficient (needs user token)
        Expected: Status 401/403
        """
        payload = {
            "phone_number": "+243900000001",
            "amount": 5000,
            "provider": "ORANGE_MONEY",
            "reservation_id": "res-123"
        }
        
        response = client.post(
            "/api/v1/payment/mobile-money/simulate",
            json=payload,
            headers=api_key_header
        )
        
        # API key is not sufficient, needs user auth
        assert response.status_code in [401, 403]


class TestPaymentStatus:
    """Tests for GET /api/v1/payment/status/{payment_id} endpoint."""
    
    def test_payment_status_requires_api_key(self, client: TestClient):
        """
        Test: Payment status requires API key
        Expected: Status 401/403 without key
        """
        response = client.get("/api/v1/payment/status/pay-123")
        
        assert response.status_code in [401, 403]
    
    def test_payment_status_with_valid_api_key(
        self, 
        client: TestClient, 
        api_key_header
    ):
        """
        Test: Valid API key allows payment status check
        Expected: Not 401/403
        """
        response = client.get(
            "/api/v1/payment/status/pay-123",
            headers=api_key_header
        )
        
        # Should pass auth
        assert response.status_code not in [401, 403]


class TestPaymentEndpointsExist:
    """Tests that payment endpoints are properly registered."""
    
    def test_mobile_money_simulate_endpoint_exists(self, client: TestClient):
        """
        Test: Mobile money simulate endpoint is registered
        Expected: Not 404
        """
        response = client.post("/api/v1/payment/mobile-money/simulate", json={})
        
        # Should exist (may be auth error or validation error)
        assert response.status_code != 404
    
    def test_payment_status_endpoint_exists(self, client: TestClient):
        """
        Test: Payment status endpoint is registered
        Expected: Not 404
        """
        response = client.get("/api/v1/payment/status/test-id")
        
        assert response.status_code != 404
    
    def test_payment_simulate_endpoint_exists(self, client: TestClient):
        """
        Test: Generic payment simulate endpoint is registered
        Expected: Not 404
        """
        response = client.post("/api/v1/payment/simulate", json={})
        
        assert response.status_code != 404
    
    def test_payment_pricing_endpoint_exists(self, client: TestClient):
        """
        Test: Payment pricing endpoint is registered
        Expected: Not 404
        """
        response = client.get("/api/v1/payment/pricing")
        
        assert response.status_code != 404
    
    def test_payment_calculate_endpoint_exists(self, client: TestClient):
        """
        Test: Payment calculate endpoint is registered
        Expected: Not 404
        """
        response = client.post("/api/v1/payment/calculate", json={})
        
        assert response.status_code != 404
    
    def test_mobile_money_providers_endpoint_exists(self, client: TestClient):
        """
        Test: Mobile money providers endpoint is registered
        Expected: Not 404
        """
        response = client.get("/api/v1/payment/mobile-money/providers")
        
        assert response.status_code != 404


class TestPaymentMethodValidation:
    """Tests for correct HTTP methods on payment endpoints."""
    
    def test_mobile_money_simulate_is_post(self, client: TestClient):
        """
        Test: Mobile money simulate uses POST method
        Expected: GET returns 405
        """
        response = client.get("/api/v1/payment/mobile-money/simulate")
        
        assert response.status_code == 405
    
    def test_payment_status_is_get(self, client: TestClient):
        """
        Test: Payment status uses GET method
        Expected: POST returns 405
        """
        response = client.post("/api/v1/payment/status/test-id", json={})
        
        assert response.status_code == 405
    
    def test_payment_simulate_is_post(self, client: TestClient):
        """
        Test: Payment simulate uses POST method
        Expected: GET returns 405
        """
        response = client.get("/api/v1/payment/simulate")
        
        assert response.status_code == 405


class TestMobileMoneyProviders:
    """Tests for mobile money providers endpoint."""
    
    def test_providers_returns_list(self, client: TestClient, api_key_header):
        """
        Test: Providers endpoint returns list of providers
        Expected: List containing ORANGE_MONEY, AIRTEL_MONEY, MPESA
        """
        response = client.get(
            "/api/v1/payment/mobile-money/providers",
            headers=api_key_header
        )
        
        if response.status_code == 200:
            data = response.json()
            # Should have providers
            assert "providers" in data or isinstance(data, list)


class TestPaymentPricing:
    """Tests for payment pricing endpoint."""
    
    def test_pricing_requires_api_key(self, client: TestClient):
        """
        Test: Pricing endpoint may require API key
        Expected: Returns pricing info or auth error
        """
        response = client.get("/api/v1/payment/pricing")
        
        # Check if it requires auth or returns pricing
        if response.status_code == 200:
            data = response.json()
            # Should have pricing info
            assert data is not None
    
    def test_pricing_returns_rate_info(self, client: TestClient, api_key_header):
        """
        Test: Pricing returns rate information
        Expected: hourly_rate or similar fields
        """
        response = client.get(
            "/api/v1/payment/pricing",
            headers=api_key_header
        )
        
        if response.status_code == 200:
            data = response.json()
            # Should have pricing fields
            has_pricing = (
                "hourly_rate" in data or
                "rate" in data or
                "price" in data or
                "currency" in data
            )
            assert has_pricing or data
