"""
AeroPark Smart System - Parking Models
Modèles de données pour les places de parking et réservations.
Compatible avec le code ESP32 existant.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ParkingSpotStatus(str, Enum):
    """États possibles d'une place de parking."""
    FREE = "free"
    OCCUPIED = "occupied"
    RESERVED = "reserved"


class ParkingSpot(BaseModel):
    """Modèle complet d'une place de parking."""
    place_id: str = Field(..., description="Identifiant de la place (ex: a1, a2)")
    etat: ParkingSpotStatus = Field(
        default=ParkingSpotStatus.FREE,
        description="État actuel de la place"
    )
    reserved_by: Optional[str] = Field(default=None, description="User ID du réservateur")
    reserved_by_email: Optional[str] = Field(default=None, description="Email du réservateur")
    reservation_start_time: Optional[datetime] = Field(default=None)
    reservation_end_time: Optional[datetime] = Field(default=None)
    reservation_duration_minutes: Optional[int] = Field(default=None)
    force_signal: Optional[int] = Field(default=None, description="Force du signal WiFi")
    last_update: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class SensorUpdateRequest(BaseModel):
    """Requête de mise à jour depuis l'ESP32 - format exact du code ESP32."""
    place_id: str = Field(..., description="Identifiant de la place (ex: a1)")
    etat: str = Field(..., description="État: 'occupied' ou 'free'")
    force_signal: Optional[int] = Field(default=None, description="RSSI WiFi")
    
    @field_validator("etat")
    @classmethod
    def validate_etat(cls, v: str) -> str:
        """Normalise et valide l'état."""
        v = v.lower().strip()
        if v not in ["occupied", "free"]:
            raise ValueError("etat doit être 'occupied' ou 'free'")
        return v


class SensorUpdateResponse(BaseModel):
    """Réponse après mise à jour du capteur."""
    success: bool
    place_id: str
    new_etat: str
    message: str
    timestamp: str


class ParkingStatusResponse(BaseModel):
    """Réponse avec l'état complet du parking."""
    total_places: int
    libres: int
    occupees: int
    reservees: int
    places: List[ParkingSpot]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ReservationRequest(BaseModel):
    """Requête de réservation d'une place."""
    place_id: str = Field(..., description="ID de la place à réserver")
    duration_minutes: int = Field(
        default=60,
        ge=15,
        le=480,
        description="Durée en minutes (15 min à 8 heures)"
    )
    vehicle_plate: Optional[str] = Field(default=None, description="Plaque d'immatriculation")


class ReservationResponse(BaseModel):
    """Réponse après une réservation."""
    success: bool
    message: str
    place_id: Optional[str] = None
    reservation_end: Optional[datetime] = None


class ReleaseRequest(BaseModel):
    """Requête pour libérer une place."""
    place_id: str = Field(..., description="ID de la place à libérer")


class WebSocketMessage(BaseModel):
    """Message WebSocket pour les réservations (format ESP32)."""
    type: str = Field(..., description="Type de message: reservation, status_update")
    donnees: Optional[dict] = Field(default=None, description="Données du message")
