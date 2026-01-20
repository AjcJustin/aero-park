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
from security.api_key import verify_sensor_api_key

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
    description="Valide un code d'accès 3 caractères pour l'ouverture de la barrière."
)
async def validate_access_code(
    request: ValidateCodeRequest,
    sensor_auth: dict = Depends(verify_sensor_api_key)
):
    """
    Valide un code d'accès pour l'entrée au parking.
    
    Utilisé par l'ESP32 quand:
    1. Le parking est plein
    2. Un véhicule est détecté à la barrière
    3. L'utilisateur saisit son code de réservation
    
    Conditions de validation:
    - Code existe et est actif
    - Code n'a pas expiré
    - Véhicule détecté (sensor_presence = true)
    """
    try:
        code_service = get_access_code_service()
        barrier_service = get_barrier_service()
        
        result = await code_service.validate_code(
            code=request.code,
            sensor_presence=request.sensor_presence
        )
        
        if result["access_granted"]:
            # Ouvrir la barrière
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
    sensor_auth: dict = Depends(verify_sensor_api_key)
):
    """
    Vérifie si l'accès à l'entrée est autorisé.
    
    Logique:
    1. Si places libres → access_granted = true
    2. Si parking plein + code valide → access_granted = true
    3. Sinon → access_granted = false avec message
    
    Utilisé par ESP32 pour la logique de barrière automatique.
    """
    try:
        barrier_service = get_barrier_service()
        
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
    sensor_auth: dict = Depends(verify_sensor_api_key)
):
    """
    Traite une demande de sortie.
    La barrière de sortie s'ouvre toujours si un véhicule est détecté.
    """
    try:
        barrier_service = get_barrier_service()
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
