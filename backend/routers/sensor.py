"""
AeroPark Smart System - Sensor Router
Gère les mises à jour des capteurs ESP32.
Endpoints utilisés: /update et /health
"""

from fastapi import APIRouter, Depends, HTTPException, status
import logging
from datetime import datetime

from models.parking import SensorUpdateRequest, SensorUpdateResponse
from security.api_key import verify_sensor_api_key
from database.firebase_db import get_db

# Configure logging
logger = logging.getLogger(__name__)

# Créer le router - Note: le préfixe /api/v1/sensor est ajouté dans main.py
router = APIRouter(
    tags=["Sensor"],
    responses={
        401: {"description": "Non autorisé - Clé API invalide"},
        400: {"description": "Requête invalide"}
    }
)


@router.post(
    "/update",
    response_model=SensorUpdateResponse,
    summary="Mise à jour depuis capteur ESP32",
    description="Reçoit les mises à jour d'état des places de parking depuis l'ESP32."
)
async def sensor_update(
    request: SensorUpdateRequest,
    _: dict = Depends(verify_sensor_api_key)
) -> SensorUpdateResponse:
    """
    Reçoit et traite les mises à jour de capteur.
    
    L'ESP32 appelle cet endpoint pour signaler l'occupation d'une place.
    L'endpoint est sécurisé avec une clé API dans le header X-API-Key.
    
    Transitions gérées:
    - 'occupied': Si place FREE → OCCUPIED, Si place RESERVED → OCCUPIED
    - 'free': Si place OCCUPIED → FREE
    
    Format de requête ESP32:
    {
        "place_id": "a1",
        "etat": "occupied" ou "free",
        "force_signal": -55
    }
    
    Returns:
        SensorUpdateResponse: Confirmation de la mise à jour
    """
    try:
        db = get_db()
        
        # Mettre à jour l'état de la place dans Firestore
        result = await db.update_place_status(
            place_id=request.place_id,
            etat=request.etat,
            force_signal=request.force_signal
        )
        
        logger.info(
            f"Capteur: place={request.place_id}, "
            f"etat={request.etat}, signal={request.force_signal}"
        )
        
        return SensorUpdateResponse(
            success=True,
            place_id=request.place_id,
            new_etat=result.get("etat"),
            message=f"Place {request.place_id} mise à jour",
            timestamp=datetime.utcnow().isoformat()
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur capteur: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du traitement de la mise à jour"
        )


@router.get(
    "/health",
    summary="Vérification de santé du backend",
    description="Endpoint appelé par l'ESP32 pour vérifier la connexion au serveur."
)
async def sensor_health(
    _: dict = Depends(verify_sensor_api_key)
):
    """
    Endpoint de vérification de santé.
    
    L'ESP32 appelle cet endpoint pour vérifier que le serveur est accessible.
    Utilisé pour le monitoring de la connexion.
    
    Returns:
        État de santé du serveur
    """
    try:
        db = get_db()
        
        # Vérifier la connexion Firestore
        places = await db.get_all_places()
        places_count = len(places)
        
        free_count = sum(1 for p in places if p.get("etat") == "free")
        occupied_count = sum(1 for p in places if p.get("etat") == "occupied")
        reserved_count = sum(1 for p in places if p.get("etat") == "reserved")
        
        return {
            "status": "healthy",
            "server_time": datetime.utcnow().isoformat(),
            "parking": {
                "total": places_count,
                "free": free_count,
                "occupied": occupied_count,
                "reserved": reserved_count
            }
        }
        
    except Exception as e:
        logger.error(f"Erreur health check: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "server_time": datetime.utcnow().isoformat()
        }


@router.get(
    "/places",
    summary="Récupérer toutes les places",
    description="Récupère l'état de toutes les places de parking."
)
async def get_all_places(
    _: dict = Depends(verify_sensor_api_key)
):
    """
    Récupère toutes les places de parking.
    
    Peut être utilisé par l'ESP32 pour synchroniser l'état initial.
    
    Returns:
        Liste de toutes les places avec leur état
    """
    try:
        db = get_db()
        places = await db.get_all_places()
        
        return {
            "success": True,
            "places": places,
            "count": len(places),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération places: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des places"
        )

