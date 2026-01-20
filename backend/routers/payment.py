"""
AeroPark Smart System - Payment Router
Endpoints pour la simulation de paiement.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
import logging
from datetime import datetime
from typing import Optional

from models.payment import (
    PaymentSimulateRequest,
    PaymentSimulateResponse,
    PaymentStatus,
    PricingInfo,
    RefundRequest,
    RefundResponse,
    MobileMoneyProvider,
    MobileMoneyRequest,
    MobileMoneyResponse,
)
from services.payment_service import get_payment_service
from services.audit_service import get_audit_service
from security.api_key import verify_sensor_api_key
from security.firebase_auth import get_current_user
from models.user import UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/payment",
    tags=["Payment"],
    responses={401: {"description": "Non autorisé"}}
)


@router.get(
    "/pricing",
    response_model=PricingInfo,
    summary="Tarification",
    description="Récupère les informations de tarification."
)
async def get_pricing():
    """
    Retourne les informations de tarification du parking.
    
    Note: Pas d'authentification requise pour consulter les tarifs.
    """
    try:
        payment_service = get_payment_service()
        pricing = await payment_service.get_pricing_info()
        
        return PricingInfo(
            hourly_rate=pricing["hourly_rate"],
            daily_max=pricing["daily_max"],
            first_minutes_free=pricing["first_minutes_free"],
            currency=pricing["currency"],
            currency_symbol=pricing["currency_symbol"]
        )
        
    except Exception as e:
        logger.error(f"Erreur récupération tarifs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de récupération des tarifs"
        )


@router.post(
    "/calculate",
    summary="Calculer montant",
    description="Calcule le montant à payer pour une durée donnée."
)
async def calculate_amount(
    hours: float = Query(..., ge=0, description="Nombre d'heures"),
    minutes: int = Query(0, ge=0, description="Minutes additionnelles")
):
    """
    Calcule le montant à payer pour une durée de stationnement.
    
    Paramètres:
    - hours: Nombre d'heures
    - minutes: Minutes supplémentaires
    
    Retourne le montant estimé.
    """
    try:
        payment_service = get_payment_service()
        total_hours = hours + (minutes / 60)
        amount = await payment_service.calculate_amount(total_hours)
        
        return {
            "duration_hours": total_hours,
            "amount": round(amount, 2),
            "currency": "USD",
            "breakdown": {
                "hourly_rate": 5.0,
                "hours_billed": max(0, total_hours - 0.25),  # 15 min gratuites
                "free_period_applied": total_hours <= 0.25
            }
        }
        
    except Exception as e:
        logger.error(f"Erreur calcul montant: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de calcul"
        )


@router.post(
    "/simulate",
    response_model=PaymentSimulateResponse,
    summary="Simuler un paiement",
    description="Simule un paiement pour une réservation."
)
async def simulate_payment(
    request: PaymentSimulateRequest,
    sensor_auth: dict = Depends(verify_sensor_api_key)
):
    """
    Simule un paiement de réservation.
    
    Le système génère un code d'accès valide si le paiement réussit.
    
    Note: Simulation uniquement - aucun paiement réel n'est effectué.
    Il y a ~5% de chance d'échec simulé pour tester les scénarios d'erreur.
    """
    try:
        payment_service = get_payment_service()
        
        # Utiliser les informations de l'authentification pour user_id et user_email
        # Pour l'ESP32/système, on utilise des valeurs par défaut
        result = await payment_service.simulate_payment(
            user_id=sensor_auth.get("sensor_id", "system"),
            user_email=f"{sensor_auth.get('sensor_id', 'system')}@aeropark.local",
            place_id=request.place_id,
            duration_minutes=request.duration_minutes,
            method=request.method,
            simulate_failure=request.simulate_failure
        )
        
        return PaymentSimulateResponse(
            success=result["success"],
            payment_id=result.get("payment_id"),
            status=result["status"] if isinstance(result["status"], PaymentStatus) else PaymentStatus(result["status"]),
            message=result["message"],
            access_code=result.get("access_code"),
            amount=result.get("amount"),
            currency=result.get("currency", "USD"),
            transaction_ref=result.get("transaction_ref"),
            reservation_confirmed=result.get("reservation_confirmed", False),
            place_id=result.get("place_id"),
            expires_at=result.get("expires_at")
        )
        
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Erreur simulation paiement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de traitement du paiement"
        )


@router.post(
    "/refund",
    response_model=RefundResponse,
    summary="Simuler un remboursement",
    description="Simule un remboursement de paiement."
)
async def refund_payment(
    request: RefundRequest,
    sensor_auth: dict = Depends(verify_sensor_api_key)
):
    """
    Simule un remboursement.
    
    Le code d'accès associé sera invalidé.
    
    Note: Simulation uniquement.
    """
    try:
        payment_service = get_payment_service()
        
        result = await payment_service.refund_payment(
            payment_id=request.payment_id,
            reason=request.reason
        )
        
        return RefundResponse(
            success=result["success"],
            payment_id=result["payment_id"],
            refund_id=result.get("refund_id"),
            amount_refunded=result.get("amount_refunded"),
            message=result["message"]
        )
        
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Erreur remboursement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de remboursement"
        )


@router.get(
    "/history/{reservation_id}",
    summary="Historique paiements",
    description="Récupère l'historique des paiements d'une réservation."
)
async def get_payment_history(
    reservation_id: str,
    sensor_auth: dict = Depends(verify_sensor_api_key)
):
    """
    Récupère tous les paiements liés à une réservation.
    """
    try:
        payment_service = get_payment_service()
        payments = await payment_service.get_payments_for_reservation(reservation_id)
        
        return {
            "reservation_id": reservation_id,
            "payments": payments,
            "total_count": len(payments),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur historique paiements: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de récupération de l'historique"
        )


@router.get(
    "/status/{payment_id}",
    summary="Statut paiement",
    description="Récupère le statut d'un paiement spécifique."
)
async def get_payment_status(
    payment_id: str,
    sensor_auth: dict = Depends(verify_sensor_api_key)
):
    """
    Récupère les détails d'un paiement par son ID.
    """
    try:
        payment_service = get_payment_service()
        payment = await payment_service.get_payment(payment_id)
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paiement non trouvé"
            )
        
        return payment
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur statut paiement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de récupération du statut"
        )


# ========== MOBILE MONEY ENDPOINTS ==========

@router.post(
    "/mobile-money/simulate",
    response_model=MobileMoneyResponse,
    summary="Simuler paiement Mobile Money",
    description="Simule un paiement via Orange Money, Airtel Money ou M-Pesa."
)
async def simulate_mobile_money(
    request: MobileMoneyRequest,
    current_user: UserProfile = Depends(get_current_user)
):
    """
    Simule un paiement Mobile Money.
    
    **Fournisseurs supportés:**
    - ORANGE_MONEY
    - AIRTEL_MONEY
    - MPESA
    
    **Simulation:**
    - 80% de chance de succès
    - 20% de chance d'échec
    
    **Si succès:**
    - Réservation passe à CONFIRMED
    - Code d'accès généré et retourné
    
    **Si échec:**
    - Réservation annulée
    - Place libérée
    
    **Note:** Ceci est une SIMULATION uniquement. Aucun paiement réel n'est effectué.
    """
    try:
        payment_service = get_payment_service()
        audit_service = get_audit_service()
        
        result = await payment_service.simulate_mobile_money_payment(
            provider=request.provider,
            phone_number=request.phone_number,
            amount=request.amount,
            reservation_id=request.reservation_id,
            user_id=current_user.uid,
            user_email=current_user.email
        )
        
        # Log l'événement de paiement
        await audit_service.log_payment_event(
            payment_id=result.get("payment_id", "unknown"),
            user_id=current_user.uid,
            amount=request.amount,
            status=result["status"].value if hasattr(result["status"], "value") else result["status"],
            provider=request.provider.value,
            phone_masked=result.get("phone_number_masked")
        )
        
        return MobileMoneyResponse(
            success=result["success"],
            payment_id=result.get("payment_id"),
            status=result["status"],
            message=result["message"],
            provider=request.provider,
            phone_number_masked=result.get("phone_number_masked"),
            amount=result.get("amount"),
            currency=result.get("currency", "USD"),
            transaction_ref=result.get("transaction_ref"),
            reservation_status=result.get("reservation_status"),
            access_code=result.get("access_code"),
            timestamp=result.get("timestamp", datetime.utcnow())
        )
        
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Erreur simulation Mobile Money: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de traitement du paiement"
        )


@router.get(
    "/mobile-money/providers",
    summary="Liste des fournisseurs Mobile Money",
    description="Retourne la liste des fournisseurs Mobile Money supportés."
)
async def get_mobile_money_providers():
    """
    Retourne les fournisseurs Mobile Money supportés.
    """
    return {
        "providers": [
            {
                "id": MobileMoneyProvider.ORANGE_MONEY.value,
                "name": "Orange Money",
                "countries": ["DR Congo","Ivory Coast", "Mali", "Cameroon", "Guinea", "Burkina Faso"],
                "icon": "orange_money"
            },
            {
                "id": MobileMoneyProvider.AIRTEL_MONEY.value,
                "name": "Airtel Money",
                "countries": ["Kenya", "Uganda", "Tanzania", "Rwanda", "DRC", "Nigeria"],
                "icon": "airtel_money"
            },
            {
                "id": MobileMoneyProvider.MPESA.value,
                "name": "M-Pesa",
                "countries": ["Kenya", "Tanzania", "DRC", "Mozambique", "Ghana", "Egypt"],
                "icon": "mpesa"
            }
        ],
        "simulation_note": "Tous les paiements sont simulés. Aucune transaction réelle n'est effectuée."
    }
