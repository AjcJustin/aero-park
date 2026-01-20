"""
AeroPark Smart System - Admin Router
Gère les opérations administratives du parking.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List
import logging
from datetime import datetime

from models.user import UserProfile
from security.firebase_auth import get_current_admin
from database.firebase_db import get_db
from services.access_code_service import get_access_code_service
from services.payment_service import get_payment_service

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


# ========== ACCESS CODE MANAGEMENT ==========

@router.get(
    "/access-codes",
    summary="Liste des codes d'accès (Admin)",
    description="Récupère tous les codes d'accès actifs."
)
async def get_all_access_codes(
    status_filter: Optional[str] = Query(None, description="Filtrer par statut: active, used, expired"),
    admin: UserProfile = Depends(get_current_admin)
):
    """Récupère tous les codes d'accès avec possibilité de filtre."""
    try:
        access_service = get_access_code_service()
        codes = await access_service.get_all_codes(status_filter=status_filter)
        
        return {
            "total": len(codes),
            "codes": codes,
            "filter_applied": status_filter,
            "admin": admin.email,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération codes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur récupération des codes"
        )


@router.post(
    "/access-codes/invalidate/{code}",
    summary="Invalider un code (Admin)",
    description="Invalide manuellement un code d'accès."
)
async def invalidate_access_code(
    code: str,
    reason: Optional[str] = None,
    admin: UserProfile = Depends(get_current_admin)
):
    """Invalide un code d'accès existant."""
    try:
        access_service = get_access_code_service()
        result = await access_service.invalidate_code(code, reason=reason or "Admin invalidation")
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["message"]
            )
        
        logger.warning(f"Admin {admin.email} a invalidé le code {code}")
        
        return {
            "success": True,
            "message": f"Code {code} invalidé",
            "admin": admin.email,
            "reason": reason or "Admin invalidation"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur invalidation code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'invalidation"
        )


@router.post(
    "/access-codes/cleanup",
    summary="Nettoyer codes expirés (Admin)",
    description="Supprime les codes expirés de la base de données."
)
async def cleanup_expired_codes(
    admin: UserProfile = Depends(get_current_admin)
):
    """Nettoie les codes d'accès expirés."""
    try:
        access_service = get_access_code_service()
        result = await access_service.cleanup_expired_codes()
        
        logger.info(f"Admin {admin.email} a nettoyé {result['cleaned_count']} codes")
        
        return {
            "success": True,
            "cleaned_count": result["cleaned_count"],
            "admin": admin.email,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur nettoyage codes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du nettoyage"
        )


# ========== RESERVATION MANAGEMENT ==========

@router.get(
    "/reservations",
    summary="Liste des réservations (Admin)",
    description="Récupère toutes les réservations."
)
async def get_all_reservations(
    status_filter: Optional[str] = Query(None, description="Filtrer par statut: active, completed, cancelled"),
    limit: int = Query(50, ge=1, le=200),
    admin: UserProfile = Depends(get_current_admin)
):
    """Récupère toutes les réservations avec filtre optionnel."""
    try:
        db = get_db()
        reservations = await db.get_all_reservations(status_filter=status_filter, limit=limit)
        
        return {
            "total": len(reservations),
            "reservations": reservations,
            "filter_applied": status_filter,
            "limit": limit,
            "admin": admin.email,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération réservations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur récupération des réservations"
        )


@router.post(
    "/reservations/cancel/{reservation_id}",
    summary="Annuler une réservation (Admin)",
    description="Annule une réservation et libère la place."
)
async def admin_cancel_reservation(
    reservation_id: str,
    reason: Optional[str] = None,
    admin: UserProfile = Depends(get_current_admin)
):
    """Annule une réservation depuis l'interface admin."""
    try:
        db = get_db()
        access_service = get_access_code_service()
        
        # Récupérer la réservation
        reservation = await db.get_reservation(reservation_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Réservation {reservation_id} non trouvée"
            )
        
        # Annuler la réservation
        await db.cancel_reservation(reservation_id)
        
        # Invalider le code d'accès associé si existant
        if reservation.get("access_code"):
            await access_service.invalidate_code(
                reservation["access_code"],
                reason="Reservation cancelled by admin"
            )
        
        # Libérer la place
        if reservation.get("place_id"):
            await db.release_place(reservation["place_id"])
        
        logger.warning(f"Admin {admin.email} a annulé la réservation {reservation_id}")
        
        return {
            "success": True,
            "message": f"Réservation {reservation_id} annulée",
            "place_freed": reservation.get("place_id"),
            "admin": admin.email,
            "reason": reason or "Admin cancellation"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur annulation réservation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'annulation"
        )


# ========== PAYMENT MANAGEMENT ==========

@router.get(
    "/payments",
    summary="Liste des paiements (Admin)",
    description="Récupère tous les paiements."
)
async def get_all_payments(
    status_filter: Optional[str] = Query(None, description="Filtrer par statut: completed, pending, failed, refunded"),
    limit: int = Query(50, ge=1, le=200),
    admin: UserProfile = Depends(get_current_admin)
):
    """Récupère tous les paiements avec filtre optionnel."""
    try:
        payment_service = get_payment_service()
        payments = await payment_service.get_all_payments(status_filter=status_filter, limit=limit)
        
        # Calculer les totaux
        total_amount = sum(p.get("amount", 0) for p in payments if p.get("status") == "completed")
        refunded_amount = sum(p.get("amount", 0) for p in payments if p.get("status") == "refunded")
        
        return {
            "total": len(payments),
            "payments": payments,
            "summary": {
                "total_collected": round(total_amount, 2),
                "total_refunded": round(refunded_amount, 2),
                "net_revenue": round(total_amount - refunded_amount, 2)
            },
            "filter_applied": status_filter,
            "admin": admin.email,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération paiements: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur récupération des paiements"
        )


@router.post(
    "/payments/refund/{payment_id}",
    summary="Rembourser un paiement (Admin)",
    description="Effectue un remboursement simulé."
)
async def admin_refund_payment(
    payment_id: str,
    reason: Optional[str] = None,
    admin: UserProfile = Depends(get_current_admin)
):
    """Rembourse un paiement depuis l'interface admin."""
    try:
        payment_service = get_payment_service()
        result = await payment_service.refund_payment(payment_id, reason=reason or "Admin refund")
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        logger.warning(f"Admin {admin.email} a remboursé le paiement {payment_id}")
        
        return {
            "success": True,
            "message": f"Paiement {payment_id} remboursé",
            "refund_id": result.get("refund_id"),
            "amount_refunded": result.get("amount_refunded"),
            "admin": admin.email,
            "reason": reason or "Admin refund"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur remboursement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du remboursement"
        )


# ========== BARRIER LOGS ==========

@router.get(
    "/barrier-logs",
    summary="Logs des barrières (Admin)",
    description="Récupère l'historique des actions des barrières."
)
async def get_barrier_logs(
    barrier_id: Optional[str] = Query(None, description="Filtrer par barrière: entry, exit"),
    limit: int = Query(50, ge=1, le=200),
    admin: UserProfile = Depends(get_current_admin)
):
    """Récupère l'historique des actions de barrière."""
    try:
        db = get_db()
        logs = await db.get_barrier_logs(barrier_id=barrier_id, limit=limit)
        
        return {
            "total": len(logs),
            "logs": logs,
            "barrier_filter": barrier_id,
            "admin": admin.email,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur récupération des logs"
        )


# ========== SYSTEM STATUS ==========

@router.get(
    "/system-status",
    summary="État du système (Admin)",
    description="Récupère l'état global du système."
)
async def get_system_status(
    admin: UserProfile = Depends(get_current_admin)
):
    """Récupère un aperçu global du système."""
    try:
        db = get_db()
        access_service = get_access_code_service()
        payment_service = get_payment_service()
        
        # Statistiques parking
        places = await db.get_all_places()
        total_places = len(places)
        free = sum(1 for p in places if p.get("etat") == "free")
        occupied = sum(1 for p in places if p.get("etat") == "occupied")
        reserved = sum(1 for p in places if p.get("etat") == "reserved")
        
        # Codes actifs
        active_codes = await access_service.get_all_codes(status_filter="active")
        
        # Paiements du jour (simulation - récupère tous)
        all_payments = await payment_service.get_all_payments(limit=100)
        today = datetime.utcnow().date()
        today_payments = [p for p in all_payments if p.get("created_at", "")[:10] == str(today)]
        
        return {
            "parking": {
                "total": total_places,
                "free": free,
                "occupied": occupied,
                "reserved": reserved,
                "occupancy_rate": round((occupied + reserved) / total_places * 100, 2) if total_places > 0 else 0
            },
            "access_codes": {
                "active_count": len(active_codes)
            },
            "payments_today": {
                "count": len(today_payments),
                "total_amount": sum(p.get("amount", 0) for p in today_payments if p.get("status") == "completed")
            },
            "system": {
                "status": "operational",
                "timestamp": datetime.utcnow().isoformat()
            },
            "admin": admin.email
        }
        
    except Exception as e:
        logger.error(f"Erreur status système: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur récupération status système"
        )
