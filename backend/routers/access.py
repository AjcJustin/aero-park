"""
AeroPark Smart System - Access Control Router
Endpoints pour la validation des codes d'accès et contrôle d'entrée.
Utilisé par l'ESP32 pour la gestion de la barrière.
"""

from fastapi import APIRouter, Depends, HTTPException, status
import logging
from datetime import datetime

from models.access import (
    ValidateCodeRequest,
    ValidateCodeResponse,
)
from services.access_code_service import get_access_code_service
from services.barrier_service import get_barrier_service
from services.websocket_service import get_websocket_manager
from security.api_key import verify_sensor_api_key
from security.firebase_auth import get_optional_user
from fastapi import Header
from typing import Optional
from config import get_settings
import secrets

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/access",
    tags=["Access Control"],
    responses={401: {"description": "Non autorisé"}}
)


@router.post(
    "/validate-code",
    response_model=ValidateCodeResponse,
    summary="Valider un code d'accès",
    description="Valide un code d'accès pour l'ouverture de la barrière."
)
async def validate_access_code(
    request: ValidateCodeRequest,
    no_open: bool = False,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    user: Optional[any] = Depends(get_optional_user)
):
    """
    Valide un code d'accès pour l'entrée au parking.
    Supporte l'authentification par Clé API (ESP32) ou JWT (Frontend).
    """
    # Vérification de l'authentification (Clé API OU User JWT)
    is_authenticated = False
    if x_api_key:
        settings = get_settings()
        if secrets.compare_digest(x_api_key, settings.sensor_api_key):
            is_authenticated = True
    
    if not is_authenticated and user:
        is_authenticated = True
        
    if not is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API manquante ou authentification requise."
        )

    try:
        code_service = get_access_code_service()
        barrier_service = get_barrier_service()
        ws_manager = get_websocket_manager()
        
        # Déterminer la présence du véhicule
        # 1. Si via App (no_open=True), on utilise toujours l'état du capteur en cache
        # 2. Si via ESP32, on utilise ce qu'il envoie, ou le cache s'il n'envoie rien (None)
        
        cached_presence = barrier_service.get_sensor_state("entry")
        actual_sensor_presence = request.sensor_presence
        
        if no_open:
            actual_sensor_presence = cached_presence
            logger.info(f"Validation via App: État capteur (cache) = {actual_sensor_presence}")
        elif actual_sensor_presence is None:
            actual_sensor_presence = cached_presence
            logger.info(f"Validation via ESP32 (champ manquant): État capteur (cache) = {actual_sensor_presence}")
        else:
            logger.info(f"Validation via ESP32: Présence capteur reçue = {actual_sensor_presence}")

        result = await code_service.validate_code(
            code=request.code,
            sensor_presence=actual_sensor_presence,
            mark_used=not no_open # Ne marquons comme utilisé que si la barrière va s'ouvrir
        )
        
        if result["access_granted"]:
            if no_open:
                # Notifier l'ESP32 que le code est validé
                await ws_manager.notify_code_validated(
                    code=request.code,
                    place_id=result.get("place_id")
                )
                logger.info(f"Code {request.code} validé via app - Notification ESP32 envoyée")
            else:
                # Ouvrir la barrière immédiatement (appelé par ESP32 directement)
                await barrier_service.open_barrier(
                    barrier_id=request.barrier_id,
                    reason="valid_code",
                    access_code=request.code,
                    place_id=result.get("place_id")
                )
                logger.info(f"Code {request.code} validé - barrière ouverte")
        else:
            logger.warning(f"Code {request.code} rejeté: {result['message']}")
        
        return ValidateCodeResponse(
            access_granted=result["access_granted"],
            message=result["message"],
            place_id=result.get("place_id"),
            user_email=result.get("user_email"),
            remaining_time_minutes=result.get("remaining_time_minutes")
        )
        
    except Exception as e:
        logger.error(f"Erreur validation code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de validation du code"
        )


@router.post(
    "/check-entry",
    summary="Vérifier l'accès à l'entrée",
    description="Vérifie si la barrière peut s'ouvrir (places libres ou code valide)."
)
async def check_entry_access(
    sensor_presence: bool = True,
    access_code: str = None,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    user: Optional[any] = Depends(get_optional_user)
):
    """
    Vérifie si l'accès à l'entrée est autorisé.
    Supporte Clé API ou JWT.
    """
    # Vérification auth
    is_auth = False
    if x_api_key:
        settings = get_settings()
        if secrets.compare_digest(x_api_key, settings.sensor_api_key):
            is_auth = True
    if not is_auth and user:
        is_auth = True
    if not is_auth:
        raise HTTPException(status_code=401, detail="Non autorisé")

    try:
        barrier_service = get_barrier_service()
        
        # Synchroniser l'état du capteur
        barrier_service.update_sensor_state("entry", sensor_presence)
        
        result = await barrier_service.check_entry_access(
            sensor_presence=sensor_presence,
            access_code=access_code
        )
        
        if result["access_granted"] and result.get("open_barrier"):
            await barrier_service.open_barrier(
                barrier_id="entry",
                reason=result.get("reason", "access_granted"),
                access_code=access_code,
                place_id=result.get("place_id")
            )
        
        return {
            "access_granted": result["access_granted"],
            "reason": result.get("reason"),
            "message": result["message"],
            "open_barrier": result.get("open_barrier", False),
            "place_id": result.get("place_id"),
            "remaining_time": result.get("remaining_time"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur check entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de vérification d'accès"
        )


@router.post(
    "/exit",
    summary="Traiter une sortie",
    description="Ouvre la barrière de sortie pour un véhicule."
)
async def process_exit(
    sensor_presence: bool = True,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    user: Optional[any] = Depends(get_optional_user)
):
    """
    Traite une demande de sortie.
    Supporte Clé API ou JWT.
    """
    # Vérification auth
    is_auth = False
    if x_api_key:
        settings = get_settings()
        if secrets.compare_digest(x_api_key, settings.sensor_api_key):
            is_auth = True
    if not is_auth and user:
        is_auth = True
    if not is_auth:
        raise HTTPException(status_code=401, detail="Non autorisé")

    try:
        barrier_service = get_barrier_service()
        
        # Synchroniser l'état du capteur
        barrier_service.update_sensor_state("exit", sensor_presence)
        
        result = await barrier_service.process_exit(sensor_presence)
        
        return {
            "access_granted": result["access_granted"],
            "message": result["message"],
            "open_barrier": result.get("open_barrier", False),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur exit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de traitement sortie"
        )
