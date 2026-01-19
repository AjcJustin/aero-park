"""
AeroPark Smart System - Admin Router
Gère les opérations administratives du parking.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
import logging
from datetime import datetime

from models.user import UserProfile
from security.firebase_auth import get_current_admin
from database.firebase_db import get_db

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/admin/parking",
    tags=["Admin"],
    responses={
        401: {"description": "Non autorisé"},
        403: {"description": "Interdit - Accès admin requis"}
    }
)


@router.get(
    "/all",
    summary="Toutes les Places (Admin)",
    description="Retourne toutes les places avec leurs détails. Accès admin requis."
)
async def get_all_places(
    admin: UserProfile = Depends(get_current_admin)
):
    """Récupère toutes les places avec détails administratifs complets."""
    try:
        db = get_db()
        places = await db.get_all_places()
        
        return {
            "total": len(places),
            "places": places,
            "admin": admin.email,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération places: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur récupération des places"
        )


@router.get(
    "/stats",
    summary="Statistiques Parking (Admin)",
    description="Retourne les statistiques détaillées du parking."
)
async def get_parking_stats(
    admin: UserProfile = Depends(get_current_admin)
):
    """Récupère les statistiques détaillées du parking."""
    try:
        db = get_db()
        places = await db.get_all_places()
        
        total = len(places)
        free = sum(1 for p in places if p.get("etat") == "free")
        occupied = sum(1 for p in places if p.get("etat") == "occupied")
        reserved = sum(1 for p in places if p.get("etat") == "reserved")
        
        occupancy_rate = ((occupied + reserved) / total * 100) if total > 0 else 0
        
        return {
            "total_places": total,
            "libres": free,
            "occupees": occupied,
            "reservees": reserved,
            "taux_occupation": round(occupancy_rate, 2),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur statistiques: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur récupération statistiques"
        )


@router.post(
    "/force-release/{place_id}",
    summary="Forcer Libération (Admin)",
    description="Force la libération d'une place."
)
async def force_release_place(
    place_id: str,
    reason: Optional[str] = None,
    admin: UserProfile = Depends(get_current_admin)
):
    """Force la libération d'une place de parking."""
    try:
        db = get_db()
        
        place = await db.get_place_by_id(place_id)
        if not place:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Place {place_id} non trouvée"
            )
        
        await db.release_place(place_id)
        
        logger.warning(f"Admin {admin.email} a forcé la libération de {place_id}")
        
        return {
            "success": True,
            "message": f"Place {place_id} libérée",
            "admin": admin.email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur libération: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la libération"
        )


@router.post(
    "/initialize",
    summary="Initialiser Places (Admin)",
    description="Initialise les places par défaut."
)
async def initialize_places(
    count: int = 6,
    admin: UserProfile = Depends(get_current_admin)
):
    """Initialise les places de parking par défaut."""
    try:
        db = get_db()
        created_ids = await db.initialize_default_places(count)
        
        if created_ids:
            return {
                "success": True,
                "message": f"{len(created_ids)} places créées",
                "place_ids": created_ids
            }
        else:
            return {
                "success": True,
                "message": "Places déjà existantes",
                "place_ids": []
            }
        
    except Exception as e:
        logger.error(f"Erreur initialisation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'initialisation"
        )
