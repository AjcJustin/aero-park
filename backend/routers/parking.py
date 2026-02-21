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
        
        total_places = len(places)
        free_count = sum(1 for p in places if p.get("etat") == "free")
        reserved_count = sum(1 for p in places if p.get("etat") == "reserved")
        occupied_count = sum(1 for p in places if p.get("etat") == "occupied")
        
        return {
            "total": total_places,
            "free_count": free_count,
            "occupied_count": occupied_count,
            "reserved_count": reserved_count,
            # For frontend compatibility
            "free": free_count,
            "occupied": occupied_count,
            "reserved": reserved_count,
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
            duration_minutes=request.duration_minutes,
            vehicle_plate=request.vehicle_plate,
            phone=request.phone,
            payment_method=request.payment_method
        )
        
        # Générer et sauvegarder le code d'accès
        access_code = None
        try:
            from services.access_code_service import get_access_code_service
            access_service = get_access_code_service()
            
            reservation_id = result.get("reservation_id")
            
            # Créer le code
            access_code = await access_service.create_access_code(
                user_id=user.uid,
                user_email=user.email,
                place_id=request.place_id,
                reservation_id=reservation_id,
                expires_at=result.get("reservation_end_time")
            )
            
            # Mettre à jour la place avec le code
            # Note: Idéalement cela devrait être fait dans la transaction de réservation
            await db.db.collection(db.COLLECTION_PLACES).document(request.place_id).update({
                "access_code": access_code
            })
            
            # Invalider le cache pour afficher le code
            from database.firebase_cache import get_firebase_cache
            cache = get_firebase_cache()
            cache.invalidate(f"parking:place:{request.place_id}")
            cache.invalidate("parking:all_places")
            
        except Exception as e:
            logger.error(f"Erreur génération code d'accès: {e}")
            # On ne bloque pas la réservation pour ça, mais c'est problématique
        
        # Préparer les données manuelles pour le broadcast immédiat (fix LCD delay)
        updated_place_data = {
            "place_id": request.place_id,
            "id": request.place_id,
            "etat": "reserved",
            "reserved_by": user.uid,
            "reserved_by_email": user.email,
            "vehicle_plate": request.vehicle_plate,
            "reservation_id": result.get("reservation_id"),
            "access_code": access_code,
            "reservation_start_time": result.get("reservation_start_time").isoformat() + "Z" if result.get("reservation_start_time") else None,
            "reservation_end_time": result.get("reservation_end_time").isoformat() + "Z" if result.get("reservation_end_time") else None,
            "last_update": datetime.utcnow().isoformat() + "Z"
        }
        
        # Notifier l'ESP32 via WebSocket avec les données manuelles
        await ws_manager.notify_reservation(request.place_id, "create", updated_place_data)
        
        logger.info(f"Réservation créée: {request.place_id} pour {user.email}")
        
        return ReservationResponse(
            success=True,
            message=f"Place {request.place_id} réservée avec succès. Code: {access_code}" if access_code else f"Place {request.place_id} réservée avec succès",
            place_id=request.place_id,
            reservation_id=reservation_id,
            reservation_end=result.get("reservation_end_time"),
            access_code=access_code 
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
        
        # Invalider le code d'accès associé
        try:
            from services.access_code_service import get_access_code_service
            access_service = get_access_code_service()
            # Chercher le code actif pour cette place
            codes = await access_service.get_all_codes(status_filter="active")
            for c in codes:
                if c.get("place_id") == place_id:
                    await access_service.invalidate_code(c["code"], "CANCELLED")
                    logger.info(f"Code {c['code']} invalidé suite à libération de {place_id}")
        except Exception as access_err:
            logger.error(f"Erreur invalidation code pour {place_id}: {access_err}")
            
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


@router.get(
    "/settings",
    summary="Paramètres Publics",
    description="Récupère les paramètres publics du système (Nom, Slogan, Contact...)."
)
async def get_public_settings():
    """
    Récupère les paramètres publics du système.
    Accessible sans authentification pour l'affichage frontend.
    """
    try:
        db = get_db()
        settings = await db.get_settings()
        
        # Déterminer le tarif selon la devise
        currency = settings.get("currency", "USD")
        
        # Determine rate based on currency, prioritizing specific rates
        if currency == "USD":
            # Taking USD rate, fallback to generic hourly_rate, fallback to default 2
            rate = settings.get("hourly_rate_usd", settings.get("hourly_rate", 2))
        else:
            # Taking FC rate, fallback to generic hourly_rate, fallback to default 1000
            rate = settings.get("hourly_rate_fc", settings.get("hourly_rate", 1000))

        # FORCE ALIGNMENT: The "generic" hourly_rate IS the rate for the active currency.
        # This fixes the issue where updating the rate in Admin (generic) doesn't update the specific field.
        active_rate_fc = settings.get("hourly_rate_fc", 1000)
        active_rate_usd = settings.get("hourly_rate_usd", 2)
        generic_rate = settings.get("hourly_rate")
        
        if generic_rate:
            if currency in ["FC", "CDF"]:
                active_rate_fc = generic_rate
            elif currency == "USD":
                active_rate_usd = generic_rate

        # Filtrer pour ne renvoyer que les infos publiques
        public_settings = {
            "parking_name": settings.get("parking_name", "AeroPark GOMA"),
            "slogan": settings.get("slogan", "Parking Automatisé"),
            "hourly_rate": rate,
            "hourly_rate_usd": active_rate_usd,
            "hourly_rate_fc": active_rate_fc,
            "exchange_rate": settings.get("exchange_rate", 2500),
            "currency": currency,
            "contact_phone": settings.get("contact_phone", ""),
            "contact_email": settings.get("contact_email", ""),
            "whatsapp": settings.get("whatsapp", ""),
            "payment_providers": settings.get("payment_providers", ["ORANGE_MONEY", "AIRTEL_MONEY", "MPESA"])
        }
        
        return public_settings
        
    except Exception as e:
        logger.error(f"Erreur récupération paramètres publics: {e}")
        # En cas d'erreur, on renvoie des valeurs par défaut pour ne pas casser le front
        return {
            "parking_name": "AeroPark GOMA",
            "slogan": "Parking Automatisé"
        }
