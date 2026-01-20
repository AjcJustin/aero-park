"""
AeroPark Smart System - Barrier Control Service
Gestion de la logique d'ouverture/fermeture des barrières.
Implements Double TRUE Rule: vehicle_presence AND valid_code for full parking.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

from database.firebase_db import get_db
from services.access_code_service import get_access_code_service
from services.websocket_service import get_websocket_manager

logger = logging.getLogger(__name__)


class BarrierService:
    """
    Service de contrôle des barrières d'entrée/sortie.
    
    Implements Double TRUE Rule:
    - Barrier opens ONLY if: vehicle_presence == TRUE AND access_code_valid == TRUE
    - Rejects code validation if vehicle_presence == FALSE
    - Rejects access if code is expired or already used
    """
    
    COLLECTION_BARRIER_LOGS = "barrier_logs"
    
    # Durée d'ouverture de la barrière en secondes
    DEFAULT_OPEN_DURATION = 10
    
    def __init__(self):
        self.db = get_db()
        self._barrier_states = {
            "entry": {"status": "closed", "last_action": None, "last_action_time": None},
            "exit": {"status": "closed", "last_action": None, "last_action_time": None}
        }
    
    async def get_parking_status(self) -> Dict[str, int]:
        """Récupère le statut du parking (places disponibles)."""
        places = await self.db.get_all_places()
        
        total = len(places)
        free = sum(1 for p in places if p.get("etat") == "free")
        reserved = sum(1 for p in places if p.get("etat") == "reserved")
        occupied = sum(1 for p in places if p.get("etat") == "occupied")
        
        return {
            "total": total,
            "free": free,
            "reserved": reserved,
            "occupied": occupied,
            "available": free  # Places vraiment libres
        }
    
    async def get_barrier_status(self, barrier_id: str = "entry") -> Dict[str, Any]:
        """
        Récupère le statut d'une barrière.
        
        Args:
            barrier_id: ID de la barrière (entry/exit)
        """
        parking = await self.get_parking_status()
        state = self._barrier_states.get(barrier_id, self._barrier_states["entry"])
        
        return {
            "barrier_id": barrier_id,
            "status": state["status"],
            "last_action": state["last_action"],
            "last_action_time": state["last_action_time"],
            "parking_available_spots": parking["free"],
            "parking_total_spots": parking["total"],
            "auto_open_allowed": parking["free"] > 0
        }
    
    async def check_entry_access(
        self,
        sensor_presence: bool = False,
        access_code: Optional[str] = None,
        esp32_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Vérifie si la barrière d'entrée peut s'ouvrir.
        
        **DOUBLE TRUE RULE** (when parking is full):
        - vehicle_presence_sensor == TRUE
        - access_code_valid == TRUE
        
        Logique:
        1. Si parking a des places libres ET véhicule présent → Ouvrir automatiquement
        2. Si parking plein → Exiger les DEUX conditions (véhicule + code valide)
        
        Args:
            sensor_presence: Présence véhicule détectée par capteur IR
            access_code: Code d'accès à 3 caractères saisi (optionnel)
            esp32_id: ID de l'ESP32 pour audit
            ip_address: Adresse IP pour audit
            
        Returns:
            Dict avec access_granted et détails
        """
        parking = await self.get_parking_status()
        
        # Import audit service here to avoid circular imports
        from services.audit_service import get_audit_service
        audit_service = get_audit_service()
        
        # CAS 1: Places libres disponibles
        if parking["free"] > 0:
            if sensor_presence:
                # Log successful auto-entry
                await audit_service.log_barrier_attempt(
                    barrier_id="entry",
                    esp32_id=esp32_id or "unknown",
                    vehicle_presence=True,
                    code=None,
                    code_valid=False,  # No code needed
                    access_granted=True,
                    reason="auto_free_spots",
                    ip_address=ip_address
                )
                
                return {
                    "access_granted": True,
                    "reason": "auto_free_spots",
                    "message": f"Bienvenue! {parking['free']} place(s) libre(s)",
                    "open_barrier": True,
                    "place_id": None,
                    "vehicle_presence": True,
                    "code_valid": None
                }
            else:
                # Log denied - no vehicle
                await audit_service.log_barrier_attempt(
                    barrier_id="entry",
                    esp32_id=esp32_id or "unknown",
                    vehicle_presence=False,
                    code=access_code,
                    code_valid=False,
                    access_granted=False,
                    reason="no_vehicle_detected",
                    ip_address=ip_address
                )
                
                return {
                    "access_granted": False,
                    "reason": "no_vehicle",
                    "message": "Aucun véhicule détecté",
                    "open_barrier": False,
                    "vehicle_presence": False,
                    "code_valid": None
                }
        
        # CAS 2: Parking plein - DOUBLE TRUE RULE APPLIES
        if parking["free"] == 0:
            # Vérifier s'il y a des réservations
            if parking["reserved"] > 0:
                # RULE: Must have BOTH vehicle presence AND valid code
                
                # Check 1: Vehicle presence is REQUIRED
                if not sensor_presence:
                    await audit_service.log_barrier_attempt(
                        barrier_id="entry",
                        esp32_id=esp32_id or "unknown",
                        vehicle_presence=False,
                        code=access_code,
                        code_valid=False,
                        access_granted=False,
                        reason="double_true_failed_no_vehicle",
                        ip_address=ip_address
                    )
                    
                    return {
                        "access_granted": False,
                        "reason": "no_vehicle",
                        "message": "Aucun véhicule détecté à la barrière",
                        "open_barrier": False,
                        "vehicle_presence": False,
                        "code_valid": None,
                        "double_true_rule": "FAILED - vehicle_presence=FALSE"
                    }
                
                # Check 2: Access code is REQUIRED
                if not access_code:
                    await audit_service.log_barrier_attempt(
                        barrier_id="entry",
                        esp32_id=esp32_id or "unknown",
                        vehicle_presence=True,
                        code=None,
                        code_valid=False,
                        access_granted=False,
                        reason="double_true_failed_no_code",
                        ip_address=ip_address
                    )
                    
                    return {
                        "access_granted": False,
                        "reason": "code_required",
                        "message": "Parking complet. Saisissez votre code de réservation.",
                        "open_barrier": False,
                        "vehicle_presence": True,
                        "code_valid": False,
                        "double_true_rule": "PENDING - awaiting code"
                    }
                
                # Check 3: Validate the code
                code_service = get_access_code_service()
                validation = await code_service.validate_code(access_code, sensor_presence)
                
                if validation["access_granted"]:
                    # BOTH CONDITIONS MET - DOUBLE TRUE SUCCESS
                    place_id = validation.get("place_id")
                    
                    # Mark code as used
                    await code_service.mark_code_used(access_code)
                    
                    # Update reserved place to occupied
                    if place_id:
                        await self.db.update_place_status(place_id, "occupied")
                    
                    await audit_service.log_barrier_attempt(
                        barrier_id="entry",
                        esp32_id=esp32_id or "unknown",
                        vehicle_presence=True,
                        code=access_code,
                        code_valid=True,
                        access_granted=True,
                        reason="double_true_success",
                        ip_address=ip_address
                    )
                    
                    return {
                        "access_granted": True,
                        "reason": "valid_reservation",
                        "message": f"Accès autorisé. Place {place_id}",
                        "open_barrier": True,
                        "place_id": place_id,
                        "remaining_time": validation.get("remaining_time_minutes"),
                        "vehicle_presence": True,
                        "code_valid": True,
                        "double_true_rule": "SUCCESS"
                    }
                else:
                    # Code invalid - log the failure reason
                    failure_reason = validation.get("message", "Code invalide")
                    
                    await audit_service.log_barrier_attempt(
                        barrier_id="entry",
                        esp32_id=esp32_id or "unknown",
                        vehicle_presence=True,
                        code=access_code,
                        code_valid=False,
                        access_granted=False,
                        reason=f"double_true_failed_invalid_code: {failure_reason}",
                        ip_address=ip_address
                    )
                    
                    # Also log code validation failure specifically
                    await audit_service.log_code_validation(
                        code=access_code,
                        valid=False,
                        reason=failure_reason,
                        esp32_id=esp32_id
                    )
                    
                    return {
                        "access_granted": False,
                        "reason": "invalid_code",
                        "message": failure_reason,
                        "open_barrier": False,
                        "vehicle_presence": True,
                        "code_valid": False,
                        "double_true_rule": f"FAILED - code_valid=FALSE ({failure_reason})"
                    }
            else:
                # Parking vraiment plein, pas de réservation
                await audit_service.log_barrier_attempt(
                    barrier_id="entry",
                    esp32_id=esp32_id or "unknown",
                    vehicle_presence=sensor_presence,
                    code=access_code,
                    code_valid=False,
                    access_granted=False,
                    reason="parking_full_no_reservations",
                    ip_address=ip_address
                )
                
                return {
                    "access_granted": False,
                    "reason": "parking_full",
                    "message": "Parking complet. Aucune place disponible.",
                    "open_barrier": False,
                    "vehicle_presence": sensor_presence,
                    "code_valid": None
                }
        
        return {
            "access_granted": False,
            "reason": "unknown",
            "message": "Erreur de vérification",
            "open_barrier": False
        }
    
    async def open_barrier(
        self,
        barrier_id: str = "entry",
        reason: str = "manual",
        user_id: Optional[str] = None,
        access_code: Optional[str] = None,
        place_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ouvre une barrière et enregistre l'événement.
        
        Args:
            barrier_id: ID de la barrière (entry/exit)
            reason: Raison de l'ouverture
            user_id: ID utilisateur (si applicable)
            access_code: Code utilisé (si applicable)
            place_id: Place associée (si applicable)
        """
        now = datetime.utcnow()
        
        # Mettre à jour l'état local
        self._barrier_states[barrier_id] = {
            "status": "open",
            "last_action": "open",
            "last_action_time": now
        }
        
        # Enregistrer l'événement
        log_entry = {
            "barrier_id": barrier_id,
            "action": "open",
            "reason": reason,
            "user_id": user_id,
            "access_code": access_code,
            "place_id": place_id,
            "timestamp": now
        }
        
        self.db.db.collection(self.COLLECTION_BARRIER_LOGS).add(log_entry)
        
        # Notifier via WebSocket
        try:
            manager = get_websocket_manager()
            await manager.broadcast({
                "type": "barrier_event",
                "barrier_id": barrier_id,
                "action": "open",
                "reason": reason,
                "place_id": place_id,
                "timestamp": now.isoformat()
            })
        except Exception as e:
            logger.error(f"Erreur notification WebSocket: {e}")
        
        logger.info(f"Barrière {barrier_id} ouverte: {reason}")
        
        return {
            "success": True,
            "barrier_id": barrier_id,
            "action": "open",
            "message": f"Barrière {barrier_id} ouverte",
            "open_duration_seconds": self.DEFAULT_OPEN_DURATION
        }
    
    async def close_barrier(self, barrier_id: str = "entry") -> Dict[str, Any]:
        """Ferme une barrière."""
        now = datetime.utcnow()
        
        self._barrier_states[barrier_id] = {
            "status": "closed",
            "last_action": "close",
            "last_action_time": now
        }
        
        # Enregistrer
        log_entry = {
            "barrier_id": barrier_id,
            "action": "close",
            "reason": "auto",
            "timestamp": now
        }
        self.db.db.collection(self.COLLECTION_BARRIER_LOGS).add(log_entry)
        
        logger.info(f"Barrière {barrier_id} fermée")
        
        return {
            "success": True,
            "barrier_id": barrier_id,
            "action": "close",
            "message": f"Barrière {barrier_id} fermée"
        }
    
    async def process_exit(self, sensor_presence: bool = True) -> Dict[str, Any]:
        """
        Traite une sortie de véhicule.
        La barrière de sortie s'ouvre toujours si véhicule détecté.
        """
        if not sensor_presence:
            return {
                "access_granted": False,
                "message": "Aucun véhicule détecté",
                "open_barrier": False
            }
        
        # Ouvrir la barrière de sortie
        await self.open_barrier("exit", "vehicle_exit")
        
        return {
            "access_granted": True,
            "message": "Bonne route!",
            "open_barrier": True,
            "barrier_id": "exit"
        }


# Instance singleton
_barrier_service: Optional[BarrierService] = None


def get_barrier_service() -> BarrierService:
    """Obtient l'instance singleton du service."""
    global _barrier_service
    if _barrier_service is None:
        _barrier_service = BarrierService()
    return _barrier_service
