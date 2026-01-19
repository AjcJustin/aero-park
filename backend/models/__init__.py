"""
AeroPark Smart System - Models Package
Contains all Pydantic models for the application.
"""

from models.parking import (
    ParkingSpotStatus,
    ParkingSpot,
    ParkingSpotCreate,
    ParkingSpotUpdate,
    ReservationRequest,
    ReservationResponse,
    SensorUpdateRequest,
    ParkingStatusResponse,
)
from models.user import (
    UserProfile,
    UserRole,
)

__all__ = [
    # Parking Models
    "ParkingSpotStatus",
    "ParkingSpot",
    "ParkingSpotCreate",
    "ParkingSpotUpdate",
    "ReservationRequest",
    "ReservationResponse",
    "SensorUpdateRequest",
    "ParkingStatusResponse",
    # User Models
    "UserProfile",
    "UserRole",
]
