"""
AeroPark Smart System - Barrier Control Router
Endpoints pour le contrôle des barrières d'entrée/sortie.
"""

from fastapi import APIRouter, Depends, HTTPException, status
import logging
from datetime import datetime

from models.access import (
    BarrierStatusResponse,
    BarrierOpenRequest,
    BarrierOpenResponse,
    BarrierStatus,
)
from services.barrier_service import get_barrier_service
from security.api_key import verify_sensor_api_key

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/barrier",
    tags=["Barrier Control"],
    responses={401: {"description": "Non autorisé"}}
)


@router.get(
    "/status",
    response_model=BarrierStatusResponse,
    summary="État de la barrière",
    description="Récupère l'état actuel de la barrière et du parking."
)
async def get_barrier_status(
    barrier_id: str = "entry",
    sensor_auth: dict = Depends(verify_sensor_api_key)
):
    """
    Récupère l'état d'une barrière.
    
    Retourne:
    - État de la barrière (open/closed)
    - Nombre de places disponibles
    - Si l'ouverture automatique est autorisée
    """
    try:
        barrier_service = get_barrier_service()
        status_data = await barrier_service.get_barrier_status(barrier_id)
        
        return BarrierStatusResponse(
            barrier_id=status_data["barrier_id"],
            status=BarrierStatus(status_data["status"]),
            last_action=status_data.get("last_action"),
            last_action_time=status_data.get("last_action_time"),
            parking_available_spots=status_data["parking_available_spots"],
            parking_total_spots=status_data["parking_total_spots"],
            auto_open_allowed=status_data["auto_open_allowed"]
        )
        
    except Exception as e:
        logger.error(f"Erreur récupération status barrière: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de récupération du statut"
        )


@router.post(
    "/open",
    response_model=BarrierOpenResponse,
    summary="Ouvrir la barrière",
    description="Demande d'ouverture de la barrière."
)
async def open_barrier(
    request: BarrierOpenRequest,
    sensor_auth: dict = Depends(verify_sensor_api_key)
):
    """
    Ouvre une barrière si les conditions sont remplies.
    
    Conditions:
    - Si reason="auto_free": Places libres disponibles + véhicule détecté
    - Si reason="code_valid": Code d'accès valide
    - Si reason="manual": Ouverture manuelle (admin)
    """
    try:
        barrier_service = get_barrier_service()
        
        # Vérifier les conditions d'ouverture
        if request.reason == "auto_free":
            # Vérifier s'il y a des places libres
            status_data = await barrier_service.get_barrier_status(request.barrier_id)
            
            if not status_data["auto_open_allowed"]:
                return BarrierOpenResponse(
                    success=False,
                    barrier_id=request.barrier_id,
                    action="denied",
                    message="Parking complet - code requis",
                    open_duration_seconds=0
                )
            
            if not request.sensor_presence:
                return BarrierOpenResponse(
                    success=False,
                    barrier_id=request.barrier_id,
                    action="denied",
                    message="Aucun véhicule détecté",
                    open_duration_seconds=0
                )
        
        elif request.reason == "code_valid":
            # La validation du code doit être faite via /access/validate-code
            if not request.code:
                return BarrierOpenResponse(
                    success=False,
                    barrier_id=request.barrier_id,
                    action="denied",
                    message="Code d'accès requis",
                    open_duration_seconds=0
                )
        
        # Ouvrir la barrière
        result = await barrier_service.open_barrier(
            barrier_id=request.barrier_id,
            reason=request.reason,
            access_code=request.code
        )
        
        return BarrierOpenResponse(
            success=result["success"],
            barrier_id=result["barrier_id"],
            action=result["action"],
            message=result["message"],
            open_duration_seconds=result["open_duration_seconds"]
        )
        
    except Exception as e:
        logger.error(f"Erreur ouverture barrière: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur d'ouverture de la barrière"
        )


@router.post(
    "/close",
    summary="Fermer la barrière",
    description="Ferme la barrière (appelé après délai)."
)
async def close_barrier(
    barrier_id: str = "entry",
    sensor_auth: dict = Depends(verify_sensor_api_key)
):
    """
    Ferme une barrière.
    Normalement appelé automatiquement après le délai d'ouverture.
    """
    try:
        barrier_service = get_barrier_service()
        result = await barrier_service.close_barrier(barrier_id)
        
        return {
            "success": result["success"],
            "barrier_id": result["barrier_id"],
            "action": result["action"],
            "message": result["message"],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur fermeture barrière: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de fermeture de la barrière"
        )


@router.get(
    "/parking-info",
    summary="Info parking pour ESP32",
    description="Informations simplifiées du parking pour l'ESP32."
)
async def get_parking_info(
    sensor_auth: dict = Depends(verify_sensor_api_key)
):
    """
    Retourne les informations essentielles pour l'ESP32.
    
    Format simplifié pour affichage LCD:
    - free_spots: nombre de places libres
    - total_spots: nombre total de places
    - allow_entry: autoriser l'entrée automatique
    """
    try:
        barrier_service = get_barrier_service()
        parking = await barrier_service.get_parking_status()
        
        return {
            "free_spots": parking["free"],
            "total_spots": parking["total"],
            "reserved_spots": parking["reserved"],
            "occupied_spots": parking["occupied"],
            "allow_entry": parking["free"] > 0,
            "parking_full": parking["free"] == 0 and parking["reserved"] == 0,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur parking info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de récupération info parking"
        )
