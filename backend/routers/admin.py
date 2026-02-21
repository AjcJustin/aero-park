"""
AeroPark Smart System - Admin Router
Gère les opérations administratives du parking.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

from models.user import UserProfile
from security.firebase_auth import get_current_admin
from database.firebase_db import get_db
from services.access_code_service import get_access_code_service
from services.access_code_service import get_access_code_service
from services.payment_service import get_payment_service
from services.websocket_service import get_websocket_manager

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
        
        # Nouvelles statistiques pour le dashboard
        all_users = await db.get_all_users(limit=500)
        
        payment_service = get_payment_service()
        all_payments = await payment_service.get_all_payments(limit=1000)
        
        # Get system currency settings
        system_settings = await db.get_settings()
        system_currency = system_settings.get("currency", "USD")
        parking_ratio = float(system_settings.get("exchange_rate", 2500))
        
        # Helper function to convert amounts based on currency
        def safe_float(val):
            try: return float(val or 0)
            except (ValueError, TypeError): return 0.0
        
        def convert_to_system_currency(amount, payment_currency):
            """Convert payment amount to system currency"""
            if not amount:
                return 0.0
            
            amt = safe_float(amount)
            cur = payment_currency or 'USD'
            
            # Heuristic: if currency says USD but amount >= 50, it's likely legacy FC data
            if cur == 'USD' and amt >= 50:
                cur = 'FC'
            
            # If same currency, no conversion needed
            if cur == system_currency:
                return amt
            
            # Convert USD to FC
            if cur == 'USD' and (system_currency == 'FC' or system_currency == 'CDF'):
                return amt * parking_ratio
            
            # Convert FC to USD
            if (cur == 'FC' or cur == 'CDF') and system_currency == 'USD':
                return amt / parking_ratio
            
            return amt
        
        # Calculate total revenue with proper currency conversion
        total_revenue = sum(
            convert_to_system_currency(p.get("amount"), p.get("currency"))
            for p in all_payments 
            if str(p.get("status")).lower() in ["success", "completed", "paid"]
        )
        
        return {
            "total_places": total,
            "libres": free,
            "occupees": occupied,
            "reservees": reserved,
            "taux_occupation": round(occupancy_rate, 2),
            "users_count": len(all_users),
            "total_revenue": total_revenue,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur statistiques: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur récupération statistiques"
        )


@router.post(
    "/barrier/force-open",
    summary="Forcer Ouverture Barrière (Admin)",
    description="Force l'ouverture de la barrière sans vérifier les capteurs. Accès admin requis."
)
async def force_open_barrier(
    barrier_id: str = "entry",
    reason: str = "ADMIN_FORCE_OPEN",
    admin: UserProfile = Depends(get_current_admin)
):
    """Force l'ouverture d'une barrière."""
    try:
        from services.barrier_service import get_barrier_service
        barrier_service = get_barrier_service()
        
        # Ouvrir la barrière (ignore les capteurs)
        result = await barrier_service.open_barrier(
            barrier_id=barrier_id,
            reason=f"FORCE_OPEN_BY_ADMIN ({admin.email})",
            user_id=admin.email
        )
        
        logger.warning(f"ACTION CRITIQUE: Admin {admin.email} a forcé l'ouverture de la barrière {barrier_id}")
        
        return {
            "success": True,
            "message": f"Ouverture forcée de la barrière {barrier_id} effectuée",
            "admin": admin.email
        }
        
    except Exception as e:
        logger.error(f"Erreur ouverture forcée barrière: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'ouverture forcée"
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
        
        # Libérer la place
        await db.release_place(place_id)
        
        # Invalider le code d'accès associé
        try:
            access_service = get_access_code_service()
            # Chercher le code actif pour cette place
            codes = await access_service.get_all_codes(status_filter="active")
            for c in codes:
                if c.get("place_id") == place_id:
                    await access_service.invalidate_code(c["code"], "ADMIN_CANCELLED")
                    logger.info(f"Code {c['code']} invalidé suite à libération de {place_id} par admin")
        except Exception as access_err:
            logger.error(f"Erreur invalidation code pour {place_id} (Admin): {access_err}")
        
        logger.warning(f"Admin {admin.email} a forcé la libération de {place_id}")
        
        # Notifier l'ESP32 et les clients web via WebSocket
        try:
            ws = get_websocket_manager()
            await ws.notify_reservation(place_id, "admin_release")
        except Exception as ws_err:
            logger.error(f"Erreur websocket notification: {ws_err}")

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


from pydantic import BaseModel

class PlaceCreate(BaseModel):
    place_id: str

@router.post(
    "/places",
    summary="Ajouter une place (Admin)",
    description="Ajoute une nouvelle place de parking."
)
async def create_place(
    place: PlaceCreate,
    admin: UserProfile = Depends(get_current_admin)
):
    """Crée une nouvelle place de parking."""
    try:
        place_id = place.place_id
        if not place_id:
            raise HTTPException(status_code=400, detail="ID de la place requis")
            
        # Nettoyer l'ID
        place_id = place_id.strip()
        if not place_id:
            raise HTTPException(status_code=400, detail="ID invalide")

        db = get_db()
        
        # Vérifier si existe déjà
        existing = await db.get_place_by_id(place_id)
        if existing:
            raise HTTPException(status_code=409, detail=f"La place {place_id} existe déjà")
            
        # Créer la place (utilise update_place_status pour la logique de création)
        # On initialise à "free"
        await db.update_place_status(place_id, "free")
        
        # Notifier via WebSocket pour mise à jour immédiate côté client (et LCD)
        try:
            ws = get_websocket_manager()
            # On diffuse un parking_update complet pour être sûr
            # Ou juste un place_update
            await ws.broadcast_place_update({
                "id": place_id,
                "place_id": place_id,
                "etat": "free",
                "status": "free"
            })
            # Et aussi rafraichir le statut global
            from services.barrier_service import get_barrier_service
            barrier_service = get_barrier_service()
            status = await barrier_service.get_parking_status()
            await ws.broadcast_parking_status(status)
            
        except Exception as ws_err:
            logger.error(f"Erreur websocket après création place: {ws_err}")
            
        logger.info(f"Admin {admin.email} a créé la place {place_id}")
        
        return {
            "success": True,
            "message": f"Place {place_id} créée avec succès",
            "place_id": place_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur création place: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la création de la place"
        )


@router.delete(
    "/places/{place_id}",
    summary="Supprimer une place (Admin)",
    description="Supprime définitivement une place de parking."
)
async def delete_place(
    place_id: str,
    admin: UserProfile = Depends(get_current_admin)
):
    """Supprime une place existante."""
    try:
        if not place_id:
            raise HTTPException(status_code=400, detail="ID de la place requis")
            
        place_id = place_id.strip()
        db = get_db()
        
        # Vérifier si existe
        existing = await db.get_place_by_id(place_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Place {place_id} introuvable")
            
        # Supprimer la place
        await db.delete_place(place_id)
        
        # Notifier via WebSocket
        try:
            ws = get_websocket_manager()
            # On envoie un event spécial pour dire que la place est supprimée
            await ws.broadcast_place_update({
                "id": place_id,
                "place_id": place_id,
                "deleted": True,
                "status": "deleted"
            })
            
            # Rafraichir le statut global
            from services.barrier_service import get_barrier_service
            barrier_service = get_barrier_service()
            status = await barrier_service.get_parking_status()
            await ws.broadcast_parking_status(status)
            
        except Exception as ws_err:
            logger.error(f"Erreur websocket après suppression place: {ws_err}")
            
        logger.info(f"Admin {admin.email} a supprimé la place {place_id}")
        
        return {
            "success": True,
            "message": f"Place {place_id} supprimée avec succès"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur suppression place: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la suppression de la place"
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
        
        # Notifier l'ESP32 et les clients web via WebSocket
        if reservation.get("place_id"):
            try:
                ws = get_websocket_manager()
                await ws.notify_reservation(reservation["place_id"], "admin_cancel")
            except Exception as ws_err:
                logger.error(f"Erreur websocket notification: {ws_err}")

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
            # Paiements du jour (somme brute)
            "payments_today": {
                "count": len(today_payments),
                "total_amount": sum(float(p.get("amount", 0)) for p in today_payments if p.get("status") == "completed")
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


@router.get(
    "/users",
    summary="Liste des utilisateurs (Admin)",
    description="Récupère la liste de tous les utilisateurs enregistrés."
)
async def get_all_users_admin(
    limit: int = Query(100, ge=1, le=500),
    admin: UserProfile = Depends(get_current_admin)
):
    """Récupère tous les utilisateurs."""
    try:
        db = get_db()
        users = await db.get_all_users(limit=limit)
        
        return {
            "total": len(users),
            "users": users,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Erreur récupération utilisateurs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur récupération des utilisateurs"
        )


# ========== SETTINGS MANAGEMENT ==========

@router.get(
    "/settings",
    summary="Récupérer paramètres (Admin)",
    description="Récupère les paramètres globaux du système."
)
async def get_system_settings(
    admin: UserProfile = Depends(get_current_admin)
):
    """Récupère les paramètres du système."""
    try:
        db = get_db()
        settings = await db.get_settings()
        return settings
    except Exception as e:
        logger.error(f"Erreur récupération paramètres: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur récupération paramètres"
        )


@router.post(
    "/settings",
    summary="Mettre à jour paramètres (Admin)",
    description="Met à jour les paramètres globaux du système."
)
async def update_system_settings(
    settings: Dict[str, Any],
    admin: UserProfile = Depends(get_current_admin)
):
    """Met à jour les paramètres du système."""
    try:
        db = get_db()
        
        # Synchronisation intelligente des tarifs
        if "hourly_rate" in settings:
            # On doit savoir quelle est la devise actuelle pour mettre à jour le bon champ spécifique
            current_currency = settings.get("currency")
            
            # Si la devise n'est pas dans le payload, on la récupère de la DB
            if not current_currency:
                existing_settings = await db.get_settings()
                current_currency = existing_settings.get("currency", "FC")
            
            # Mise à jour du champ spécifique correspondant
            if current_currency in ["FC", "CDF"]:
                settings["hourly_rate_fc"] = settings["hourly_rate"]
            elif current_currency == "USD":
                settings["hourly_rate_usd"] = settings["hourly_rate"]
                
        await db.save_settings(settings)
        
        # Notifier via WebSocket
        try:
            ws = get_websocket_manager()
            await ws.broadcast({
                "type": "settings_update",
                "settings": settings
            })
        except Exception as ws_err:
            logger.error(f"Erreur websocket après update settings: {ws_err}")
            
        logger.info(f"Admin {admin.email} a mis à jour les paramètres")
        
        return {
            "success": True,
            "message": "Paramètres mis à jour avec succès",
            "settings": settings
        }
        
    except Exception as e:
        logger.error(f"Erreur mise à jour paramètres: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur mise à jour paramètres"
        )


@router.post("/users/block/{user_id}")
async def block_user(
    user_id: str,
    admin: UserProfile = Depends(get_current_admin)
):
    """Bloque un utilisateur."""
    db = get_db()
    if await db.update_user_status(user_id, True):
        return {"success": True, "message": f"Utilisateur {user_id} bloqué"}
    raise HTTPException(status_code=500, detail="Erreur lors du blocage")


@router.post("/users/unblock/{user_id}")
async def unblock_user(
    user_id: str,
    admin: UserProfile = Depends(get_current_admin)
):
    """Débloque un utilisateur."""
    db = get_db()
    if await db.update_user_status(user_id, False):
        return {"success": True, "message": f"Utilisateur {user_id} débloqué"}
    raise HTTPException(status_code=500, detail="Erreur lors du déblocage")


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: UserProfile = Depends(get_current_admin)
):
    """Supprime un utilisateur."""
    db = get_db()
    if await db.delete_user(user_id):
        return {"success": True, "message": f"Utilisateur {user_id} supprimé"}
    raise HTTPException(status_code=500, detail="Erreur lors de la suppression")
@router.get("/settings")
async def get_settings_admin(
    admin: UserProfile = Depends(get_current_admin)
):
    """Récupère les paramètres du système."""
    db = get_db()
    settings = await db.get_system_settings()
    return settings or {
        "parking_name": "AeroPark GOMA",
        "slogan": "Parking Automatisé",
        "hourly_rate": 2,
        "currency": "USD",
        "exchange_rate": 2500,  # 1 USD = 2500 FC
        "max_duration": 170
    }

@router.post("/settings")
async def update_settings_admin(
    settings_data: Dict[str, Any],
    admin: UserProfile = Depends(get_current_admin)
):
    """Met à jour les paramètres du système."""
    db = get_db()
    if await db.update_system_settings(settings_data):
        return {"success": True, "message": "Paramètres mis à jour"}
    raise HTTPException(status_code=500, detail="Erreur lors de la mise à jour")


@router.post(
    "/system/reset",
    summary="Réinitialiser le système (Admin)",
    description="⚠️ ACTION DESTRUCTIVE: Efface réservations, paiements, logs et utilisateurs clients. Remet les places à zéro. Garde l'admin courant."
)
async def reset_system(
    admin: UserProfile = Depends(get_current_admin)
):
    """Réinitialise toutes les données du système."""
    try:
        db = get_db()
        stats = await db.reset_system_data(keep_admin_email=admin.email)
        
        logger.warning(f"SYSTEM RESET déclenché par admin {admin.email}. Stats: {stats}")
        
        return {
            "success": True,
            "message": "Système réinitialisé avec succès",
            "stats": stats,
            "admin": admin.email
        }
    except Exception as e:
        logger.error(f"Erreur endpoint reset: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la réinitialisation du système"
        )
