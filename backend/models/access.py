"""
AeroPark Smart System - Access Control Models
Modèles pour les codes d'accès et la gestion des barrières.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class AccessCodeStatus(str, Enum):
    """États possibles d'un code d'accès."""
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class AccessCode(BaseModel):
    """Modèle d'un code d'accès pour la barrière."""
    code: str = Field(..., min_length=3, max_length=3, description="Code 3 caractères alphanumériques")
    user_id: str = Field(..., description="UID Firebase de l'utilisateur")
    user_email: str = Field(..., description="Email de l'utilisateur")
    place_id: str = Field(..., description="ID de la place réservée")
    reservation_id: str = Field(..., description="ID de la réservation")
    status: AccessCodeStatus = Field(default=AccessCodeStatus.ACTIVE)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(..., description="Date d'expiration du code")
    used_at: Optional[datetime] = Field(default=None, description="Date d'utilisation")
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ValidateCodeRequest(BaseModel):
    """Requête de validation de code d'accès depuis ESP32."""
    code: str = Field(..., min_length=3, max_length=3, description="Code à valider")
    sensor_presence: bool = Field(..., description="Présence véhicule détectée par capteur")
    barrier_id: str = Field(default="entry", description="ID de la barrière (entry/exit)")


class ValidateCodeResponse(BaseModel):
    """Réponse de validation du code d'accès."""
    access_granted: bool
    message: str
    place_id: Optional[str] = None
    user_email: Optional[str] = None
    remaining_time_minutes: Optional[int] = None


class BarrierStatus(str, Enum):
    """États possibles de la barrière."""
    OPEN = "open"
    CLOSED = "closed"
    ERROR = "error"


class BarrierStatusResponse(BaseModel):
    """État actuel de la barrière."""
    barrier_id: str
    status: BarrierStatus
    last_action: Optional[str] = None
    last_action_time: Optional[datetime] = None
    parking_available_spots: int
    parking_total_spots: int
    auto_open_allowed: bool = Field(description="True si places libres disponibles")


class BarrierOpenRequest(BaseModel):
    """Requête d'ouverture de barrière."""
    barrier_id: str = Field(default="entry")
    reason: str = Field(default="manual", description="Raison: manual, code_valid, auto_free")
    code: Optional[str] = Field(default=None, description="Code d'accès si applicable")
    sensor_presence: bool = Field(default=False, description="Présence véhicule")


class BarrierOpenResponse(BaseModel):
    """Réponse d'ouverture de barrière."""
    success: bool
    barrier_id: str
    action: str
    message: str
    open_duration_seconds: int = Field(default=10)


class EntryCheckRequest(BaseModel):
    """Requête de vérification d'entrée depuis ESP32."""
    sensor_presence: bool = Field(..., description="Véhicule détecté au capteur d'entrée")
    barrier_id: str = Field(default="entry")


class EntryCheckResponse(BaseModel):
    """Réponse de vérification d'entrée."""
    can_enter: bool
    reason: str = Field(description="auto_free, code_required, parking_full")
    message: str
    require_code: bool
    free_spots: int
    total_spots: int


class ExitRequest(BaseModel):
    """Requête de sortie depuis ESP32."""
    sensor_presence: bool = Field(..., description="Véhicule détecté au capteur de sortie")
    barrier_id: str = Field(default="exit")


class ExitResponse(BaseModel):
    """Réponse de sortie."""
    success: bool
    barrier_id: str
    action: str
    message: str
    open_duration_seconds: int = Field(default=10)
