"""
AeroPark Smart System - Test Configuration & Fixtures
Reusable fixtures for all test modules.

Usage:
    pytest tests/ -v
    pytest tests/test_sensor.py -v
    pytest tests/ -v --tb=short
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# MOCK FIREBASE BEFORE IMPORTING APP
# ============================================================

@pytest.fixture(scope="session", autouse=True)
def mock_firebase():
    """Mock Firebase initialization at session level."""
    with patch("database.firebase_db.init_firebase") as mock_init:
        with patch("database.firebase_db.get_firestore_client") as mock_client:
            mock_init.return_value = MagicMock()
            mock_client.return_value = MagicMock()
            yield


# ============================================================
# API KEY FIXTURES
# ============================================================

@pytest.fixture
def api_key() -> str:
    """Valid API key for sensor/barrier endpoints."""
    return "aeropark-sensor-key-2024"


@pytest.fixture
def invalid_api_key() -> str:
    """Invalid API key for testing rejection."""
    return "invalid-key-12345"


@pytest.fixture
def api_key_header(api_key: str) -> dict:
    """Headers with valid API key (singular naming for convenience)."""
    return {"X-API-Key": api_key}


@pytest.fixture
def api_key_headers(api_key: str) -> dict:
    """Headers with valid API key."""
    return {"X-API-Key": api_key}


@pytest.fixture
def invalid_api_key_header(invalid_api_key: str) -> dict:
    """Headers with invalid API key."""
    return {"X-API-Key": invalid_api_key}


@pytest.fixture
def invalid_api_key_headers(invalid_api_key: str) -> dict:
    """Headers with invalid API key."""
    return {"X-API-Key": invalid_api_key}


# ============================================================
# MOCK DATABASE FIXTURES
# ============================================================

@pytest.fixture
def mock_db():
    """Mock database with common methods."""
    mock = MagicMock()
    
    # Default parking places
    mock.get_all_places = AsyncMock(return_value=[
        {"place_id": "a1", "etat": "free", "reserved_by": None},
        {"place_id": "a2", "etat": "free", "reserved_by": None},
        {"place_id": "a3", "etat": "occupied", "reserved_by": None},
        {"place_id": "a4", "etat": "reserved", "reserved_by": "user123"},
        {"place_id": "a5", "etat": "free", "reserved_by": None},
        {"place_id": "a6", "etat": "free", "reserved_by": None},
    ])
    
    mock.get_place_by_id = AsyncMock(side_effect=lambda place_id: {
        "a1": {"place_id": "a1", "etat": "free", "reserved_by": None},
        "a2": {"place_id": "a2", "etat": "free", "reserved_by": None},
        "a3": {"place_id": "a3", "etat": "occupied", "reserved_by": None},
        "a4": {"place_id": "a4", "etat": "reserved", "reserved_by": "user123"},
        "a5": {"place_id": "a5", "etat": "free", "reserved_by": None},
        "a6": {"place_id": "a6", "etat": "free", "reserved_by": None},
    }.get(place_id))
    
    mock.update_place_status = AsyncMock(return_value={"etat": "occupied"})
    mock.reserve_place = AsyncMock(return_value={
        "success": True,
        "place_id": "a1",
        "reservation_id": "res-123"
    })
    mock.release_place = AsyncMock(return_value=True)
    mock.initialize_default_places = AsyncMock(return_value=["a1", "a2", "a3", "a4", "a5", "a6"])
    
    return mock


@pytest.fixture
def mock_full_parking_db():
    """Mock database with all places occupied (full parking)."""
    mock = MagicMock()
    
    mock.get_all_places = AsyncMock(return_value=[
        {"place_id": "a1", "etat": "occupied", "reserved_by": None},
        {"place_id": "a2", "etat": "occupied", "reserved_by": None},
        {"place_id": "a3", "etat": "occupied", "reserved_by": None},
        {"place_id": "a4", "etat": "reserved", "reserved_by": "user123"},
        {"place_id": "a5", "etat": "occupied", "reserved_by": None},
        {"place_id": "a6", "etat": "occupied", "reserved_by": None},
    ])
    
    mock.get_place_by_id = AsyncMock(return_value={
        "place_id": "a1", "etat": "occupied", "reserved_by": None
    })
    
    return mock


# ============================================================
# MOCK USER FIXTURES
# ============================================================

@pytest.fixture
def mock_user():
    """Mock regular user profile."""
    return MagicMock(
        uid="user-123",
        email="testuser@example.com",
        role="user",
        is_admin=False
    )


@pytest.fixture
def mock_admin():
    """Mock admin user profile."""
    return MagicMock(
        uid="admin-123",
        email="admin@aeropark.com",
        role="admin",
        is_admin=True
    )


# ============================================================
# TEST CLIENT FIXTURE
# ============================================================

@pytest.fixture
def client(mock_db):
    """FastAPI TestClient with mocked dependencies."""
    # Patch Firebase and DB before importing app
    with patch("database.firebase_db.init_firebase"):
        with patch("database.firebase_db.get_db", return_value=mock_db):
            with patch("utils.scheduler.start_scheduler"):
                with patch("utils.scheduler.stop_scheduler"):
                    from main import app
                    with TestClient(app) as test_client:
                        yield test_client


@pytest.fixture
def client_full_parking(mock_full_parking_db):
    """TestClient with full parking simulation."""
    with patch("database.firebase_db.init_firebase"):
        with patch("database.firebase_db.get_db", return_value=mock_full_parking_db):
            with patch("utils.scheduler.start_scheduler"):
                with patch("utils.scheduler.stop_scheduler"):
                    from main import app
                    with TestClient(app) as test_client:
                        yield test_client


# ============================================================
# ACCESS CODE FIXTURES
# ============================================================

@pytest.fixture
def valid_access_code() -> str:
    """A valid 3-character access code."""
    return "A7F"


@pytest.fixture
def expired_access_code() -> str:
    """An expired access code."""
    return "X9Z"


@pytest.fixture
def mock_access_code_service():
    """Mock access code service."""
    mock = MagicMock()
    
    mock.validate_code = AsyncMock(return_value={
        "access_granted": True,
        "message": "Code valide - Accès autorisé",
        "place_id": "a1",
        "user_email": "user@example.com",
        "remaining_time_minutes": 55
    })
    
    mock.generate_code = AsyncMock(return_value={
        "code": "A7F",
        "expires_at": "2026-01-20T12:00:00Z",
        "place_id": "a1"
    })
    
    return mock


# ============================================================
# PAYMENT FIXTURES
# ============================================================

@pytest.fixture
def mock_payment_service():
    """Mock payment service."""
    mock = MagicMock()
    
    mock.simulate_payment = AsyncMock(return_value={
        "success": True,
        "payment_id": "PAY-123456",
        "status": "success",
        "message": "Paiement simulé avec succès",
        "access_code": "A7F",
        "amount": 500,
        "currency": "XAF"
    })
    
    mock.get_pricing_info = AsyncMock(return_value={
        "hourly_rate": 100,
        "daily_max": 1000,
        "first_minutes_free": 15,
        "currency": "XAF",
        "currency_symbol": "FCFA"
    })
    
    mock.get_payment = AsyncMock(return_value={
        "payment_id": "PAY-123456",
        "status": "success",
        "amount": 500
    })
    
    return mock


# ============================================================
# BARRIER SERVICE FIXTURES
# ============================================================

@pytest.fixture
def mock_barrier_service():
    """Mock barrier service."""
    mock = MagicMock()
    
    mock.open_barrier = AsyncMock(return_value=True)
    mock.close_barrier = AsyncMock(return_value=True)
    mock.check_entry_access = AsyncMock(return_value={
        "access_granted": True,
        "reason": "spots_available",
        "message": "Bienvenue! Places disponibles.",
        "open_barrier": True,
        "free_spots": 4
    })
    
    return mock


# ============================================================
# SAMPLE TEST DATA
# ============================================================

@pytest.fixture
def sensor_update_payload() -> dict:
    """Valid sensor update payload."""
    return {
        "place_id": "a1",
        "etat": "occupied",
        "force_signal": -55
    }


@pytest.fixture
def mobile_money_payload() -> dict:
    """Valid mobile money simulation payload."""
    return {
        "provider": "ORANGE_MONEY",
        "phone_number": "0612345678",
        "amount": 500,
        "reservation_id": "a1"
    }


@pytest.fixture
def validate_code_payload(valid_access_code: str) -> dict:
    """Valid code validation payload."""
    return {
        "code": valid_access_code,
        "sensor_presence": True,
        "barrier_id": "entry"
    }
