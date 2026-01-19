"""
AeroPark Smart System - Parking Router
Gère l'état du parking, les réservations et les libérations.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import logging
from datetime import datetime

from models.parking import (
    ReservationRequest,
    ReservationResponse,
)
from models.user import UserProfile
from security.firebase_auth import get_current_user
from database.firebase_db import get_db
from services.websocket_service import get_websocket_manager

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/parking",
    tags=["Parking"],
    responses={401: {"description": "Non autorisé"}}
)


@router.get(
    "/status",
    summary="État du Parking",
    description="Retourne l'état actuel de toutes les places de parking."
)
async def get_parking_status():
    """
    Obtenir l'état actuel de toutes les places de parking.
    
    Endpoint public qui retourne:
    - Nombre total de places
    - Compteurs: libres, réservées, occupées
    - Liste complète de toutes les places
    """
    try:
        db = get_db()
        places = await db.get_all_places()
        
        free = sum(1 for p in places if p.get("etat") == "free")
        reserved = sum(1 for p in places if p.get("etat") == "reserved")
        occupied = sum(1 for p in places if p.get("etat") == "occupied")
        
        return {
            "total": len(places),
            "free": free,
            "reserved": reserved,
            "occupied": occupied,
            "places": places,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération état parking: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur récupération état parking"
        )


@router.get(
    "/available",
    summary="Places Disponibles",
    description="Retourne les places disponibles pour réservation."
)
async def get_available_places():
    """
    Obtenir toutes les places de parking disponibles.
    
    Retourne uniquement les places avec état 'free'.
    """
    try:
        db = get_db()
        places = await db.get_all_places()
        
        available = [p for p in places if p.get("etat") == "free"]
        
        return {
            "available": available,
            "count": len(available),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération places disponibles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur récupération places disponibles"
        )


@router.get(
    "/place/{place_id}",
    summary="Détails d'une Place",
    description="Retourne les informations détaillées d'une place spécifique."
)
async def get_place_details(place_id: str):
    """
    Obtenir les détails d'une place de parking.
    
    Args:
        place_id: ID de la place (ex: a1, a2)
        
    Returns:
        Détails complets de la place
    """
    try:
        db = get_db()
        place = await db.get_place_by_id(place_id)
        
        if not place:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Place {place_id} non trouvée"
            )
        
        return place
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération place {place_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur récupération détails place"
        )


@router.post(
    "/reserve",
    response_model=ReservationResponse,
    summary="Réserver une Place",
    description="Réserve une place de parking disponible."
)
async def reserve_place(
    request: ReservationRequest,
    user: UserProfile = Depends(get_current_user)
) -> ReservationResponse:
    """
    Réserver une place de parking.
    
    Les utilisateurs authentifiés peuvent réserver une place disponible
    pour une durée spécifiée (15 min à 8 heures).
    
    Cette action envoie une notification WebSocket à l'ESP32.
    
    Args:
        request: Requête avec place_id et duration_minutes
        user: Utilisateur authentifié
        
    Returns:
        ReservationResponse: Confirmation de réservation
    """
    try:
        db = get_db()
        ws_manager = get_websocket_manager()
        
        # Vérifier la durée
        if request.duration_minutes < 15 or request.duration_minutes > 480:
            return ReservationResponse(
                success=False,
                message="Durée doit être entre 15 et 480 minutes"
            )
        
        # Réserver la place
        result = await db.reserve_place(
            place_id=request.place_id,
            user_id=user.uid,
            user_email=user.email,
            duration_minutes=request.duration_minutes
        )
        
        # Notifier l'ESP32 via WebSocket
        await ws_manager.notify_reservation(request.place_id, "create")
        
        logger.info(f"Réservation créée: {request.place_id} pour {user.email}")
        
        return ReservationResponse(
            success=True,
            message=f"Place {request.place_id} réservée avec succès",
            place_id=request.place_id,
            reservation_end=result.get("reservation_end_time")
        )
        
    except ValueError as e:
        return ReservationResponse(
            success=False,
            message=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur création réservation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la réservation"
        )


@router.post(
    "/release/{place_id}",
    summary="Libérer une Place",
    description="Libère une place réservée ou occupée."
)
async def release_place(
    place_id: str,
    user: UserProfile = Depends(get_current_user)
):
    """
    Libérer une place de parking.
    
    Permet aux utilisateurs de libérer manuellement leur place.
    Envoie une notification WebSocket à l'ESP32.
    
    Args:
        place_id: ID de la place à libérer
        user: Utilisateur authentifié
        
    Returns:
        Confirmation de libération
    """
    try:
        db = get_db()
        ws_manager = get_websocket_manager()
        
        # Vérifier que la place appartient à l'utilisateur
        place = await db.get_place_by_id(place_id)
        
        if not place:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Place {place_id} non trouvée"
            )
        
        if place.get("reserved_by") != user.uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous ne pouvez libérer que vos propres réservations"
            )
        
        # Libérer la place
        await db.release_place(place_id)
        
        # Notifier l'ESP32
        await ws_manager.notify_reservation(place_id, "cancel")
        
        logger.info(f"Place {place_id} libérée par {user.email}")
        
        return {
            "success": True,
            "message": f"Place {place_id} libérée avec succès"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur libération place: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la libération"
        )


@router.get(
    "/my-reservation",
    summary="Ma Réservation",
    description="Récupère la réservation active de l'utilisateur."
)
async def get_my_reservation(
    user: UserProfile = Depends(get_current_user)
):
    """
    Récupère la réservation active de l'utilisateur.
    
    Returns:
        Détails de la réservation active ou null
    """
    try:
        db = get_db()
        reservation = await db.get_user_active_reservation(user.uid)
        
        return {
            "has_reservation": reservation is not None,
            "reservation": reservation,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération réservation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur récupération réservation"
        )
