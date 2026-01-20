"""
AeroPark Smart System - Models Package
Contient tous les modèles Pydantic pour l'application.
"""

from models.parking import (
    ParkingSpotStatus,
    ReservationStatus,
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
from models.access import (
    AccessCode,
    AccessCodeStatus,
    ValidateCodeRequest,
    ValidateCodeResponse,
    BarrierStatus,
    BarrierStatusResponse,
    BarrierOpenRequest,
    BarrierOpenResponse,
    EntryCheckRequest,
    EntryCheckResponse,
    ExitRequest,
    ExitResponse,
)
from models.payment import (
    PaymentRecord,
    PaymentStatus,
    PaymentMethod,
    MobileMoneyProvider,
    PaymentSimulateRequest,
    PaymentSimulateResponse,
    PricingInfo,
    RefundRequest,
    RefundResponse,
    MobileMoneyRequest,
    MobileMoneyResponse,
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
    # Access Models
    "AccessCode",
    "AccessCodeStatus",
    "ValidateCodeRequest",
    "ValidateCodeResponse",
    "BarrierStatus",
    "BarrierStatusResponse",
    "BarrierOpenRequest",
    "BarrierOpenResponse",
    "EntryCheckRequest",
    "EntryCheckResponse",
    "ExitRequest",
    "ExitResponse",
    # Payment Models
    "PaymentRecord",
    "PaymentStatus",
    "PaymentMethod",
    "MobileMoneyProvider",
    "PaymentSimulateRequest",
    "PaymentSimulateResponse",
    "PricingInfo",
    "RefundRequest",
    "RefundResponse",
    "MobileMoneyRequest",
    "MobileMoneyResponse",
    # Reservation Status
    "ReservationStatus",
]

