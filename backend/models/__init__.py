"""
AeroPark Smart System - Models Package
Contient tous les modèles Pydantic pour l'application.
"""

from models.parking import (
    ParkingSpotStatus,
    ParkingSpot,
    SensorUpdateRequest,
    SensorUpdateResponse,
    ParkingStatusResponse,
    ReservationRequest,
    ReservationResponse,
    ReleaseRequest,
    WebSocketMessage,
)
from models.user import (
    UserProfile,
    UserRole,
)

__all__ = [
    # Parking Models
    "ParkingSpotStatus",
    "ParkingSpot",
    "SensorUpdateRequest",
    "SensorUpdateResponse",
    "ParkingStatusResponse",
    "ReservationRequest",
    "ReservationResponse",
    "ReleaseRequest",
    "WebSocketMessage",
    # User Models
    "UserProfile",
    "UserRole",
]

