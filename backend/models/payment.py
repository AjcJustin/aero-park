"""
AeroPark Smart System - Payment Models
Modèles pour la simulation de paiement.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum
import re


class PaymentStatus(str, Enum):
    """États possibles d'un paiement."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    """Méthodes de paiement simulées."""
    CARD = "card"
    MOBILE = "mobile"
    CASH = "cash"


class MobileMoneyProvider(str, Enum):
    """Fournisseurs Mobile Money africains."""
    ORANGE_MONEY = "ORANGE_MONEY"
    AIRTEL_MONEY = "AIRTEL_MONEY"
    MPESA = "MPESA"


class PaymentRecord(BaseModel):
    """Enregistrement d'un paiement."""
    payment_id: str = Field(..., description="ID unique du paiement")
    user_id: str = Field(..., description="UID Firebase de l'utilisateur")
    user_email: Optional[str] = Field(default=None, description="Email de l'utilisateur")
    reservation_id: Optional[str] = Field(default=None, description="ID de la réservation associée")
    place_id: Optional[str] = Field(default=None, description="ID de la place réservée")
    amount: float = Field(..., ge=0, description="Montant en devise locale")
    currency: str = Field(default="USD", description="Devise")
    method: PaymentMethod = Field(default=PaymentMethod.CARD)
    provider: Optional[MobileMoneyProvider] = Field(default=None, description="Fournisseur Mobile Money")
    phone_number: Optional[str] = Field(default=None, description="Numéro de téléphone pour Mobile Money")
    status: PaymentStatus = Field(default=PaymentStatus.PENDING)
    duration_minutes: Optional[int] = Field(default=None, description="Durée de réservation en minutes")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    transaction_ref: Optional[str] = Field(default=None, description="Référence transaction simulée")
    failure_reason: Optional[str] = Field(default=None)
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class PaymentSimulateRequest(BaseModel):
    """Requête de simulation de paiement."""
    place_id: str = Field(..., description="ID de la place à réserver")
    duration_minutes: int = Field(
        default=60,
        ge=15,
        le=480,
        description="Durée en minutes (15 min à 8 heures)"
    )
    method: PaymentMethod = Field(default=PaymentMethod.CARD)
    card_number: Optional[str] = Field(default=None, description="Numéro carte simulé (4 derniers)")
    simulate_failure: bool = Field(default=False, description="Forcer un échec pour test")


class PaymentSimulateResponse(BaseModel):
    """Réponse de simulation de paiement."""
    success: bool
    payment_id: Optional[str] = None
    status: PaymentStatus
    message: str
    amount: Optional[float] = None
    currency: str = "USD"
    transaction_ref: Optional[str] = None
    reservation_confirmed: bool = False
    access_code: Optional[str] = Field(default=None, description="Code d'accès si paiement réussi")
    place_id: Optional[str] = None
    expires_at: Optional[datetime] = None


class PricingInfo(BaseModel):
    """Information sur la tarification."""
    base_rate_per_hour: float = Field(default=5.0)
    hourly_rate: float = Field(default=5.0)
    daily_max: float = Field(default=30.0)
    first_minutes_free: int = Field(default=15)
    currency: str = Field(default="USD")
    currency_symbol: str = Field(default="$")
    minimum_duration_minutes: int = Field(default=15)
    maximum_duration_minutes: int = Field(default=480)
    
    def calculate_price(self, duration_minutes: int) -> float:
        """Calcule le prix pour une durée donnée."""
        hours = max(duration_minutes / 60, 0.25)  # Minimum 15 min = 0.25h
        return round(hours * self.base_rate_per_hour, 2)


class RefundRequest(BaseModel):
    """Requête de remboursement."""
    payment_id: str = Field(..., description="ID du paiement à rembourser")
    reason: Optional[str] = Field(default=None, description="Raison du remboursement")


class RefundResponse(BaseModel):
    """Réponse de remboursement."""
    success: bool
    payment_id: str
    refund_id: Optional[str] = None
    amount_refunded: Optional[float] = None
    message: str


# ========== MOBILE MONEY MODELS ==========

class MobileMoneyRequest(BaseModel):
    """Requête de paiement Mobile Money."""
    provider: MobileMoneyProvider = Field(..., description="Fournisseur: ORANGE_MONEY, AIRTEL_MONEY, MPESA")
    phone_number: str = Field(..., min_length=8, max_length=15, description="Numéro de téléphone")
    amount: float = Field(..., gt=0, description="Montant à payer")
    reservation_id: str = Field(..., description="ID de la réservation")
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        # Remove spaces and dashes
        cleaned = re.sub(r'[\s\-]', '', v)
        # Must start with + or digits
        if not re.match(r'^(\+)?[0-9]{8,15}$', cleaned):
            raise ValueError('Numéro de téléphone invalide')
        return cleaned


class MobileMoneyResponse(BaseModel):
    """Réponse de paiement Mobile Money."""
    success: bool
    payment_id: Optional[str] = None
    status: PaymentStatus
    message: str
    provider: MobileMoneyProvider
    phone_number_masked: Optional[str] = Field(default=None, description="Numéro masqué (****1234)")
    amount: Optional[float] = None
    currency: str = "USD"
    transaction_ref: Optional[str] = None
    reservation_status: Optional[str] = Field(default=None, description="CONFIRMED ou CANCELLED")
    access_code: Optional[str] = Field(default=None, description="Code d'accès si paiement réussi")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
