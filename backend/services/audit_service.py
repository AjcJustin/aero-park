"""
AeroPark Smart System - Audit Logging Service
Service de journalisation des audits pour la sécurité et le monitoring.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from database.firebase_db import get_db

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types d'événements d'audit."""
    # Barrier Events
    BARRIER_OPEN_REQUEST = "barrier_open_request"
    BARRIER_OPEN_SUCCESS = "barrier_open_success"
    BARRIER_OPEN_DENIED = "barrier_open_denied"
    BARRIER_CLOSE = "barrier_close"
    
    # Access Code Events
    CODE_VALIDATION_SUCCESS = "code_validation_success"
    CODE_VALIDATION_FAILED = "code_validation_failed"
    CODE_EXPIRED = "code_expired"
    CODE_ALREADY_USED = "code_already_used"
    CODE_GENERATED = "code_generated"
    CODE_INVALIDATED = "code_invalidated"
    
    # Sensor Events
    SENSOR_UPDATE = "sensor_update"
    SENSOR_INCONSISTENCY = "sensor_inconsistency"
    
    # ESP32 Events
    ESP32_HEARTBEAT = "esp32_heartbeat"
    ESP32_CONNECTION = "esp32_connection"
    ESP32_DISCONNECTION = "esp32_disconnection"
    ESP32_ERROR = "esp32_error"
    
    # Payment Events
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_REFUNDED = "payment_refunded"
    
    # Entry/Exit Events
    ENTRY_ALLOWED = "entry_allowed"
    ENTRY_DENIED = "entry_denied"
    EXIT_PROCESSED = "exit_processed"


class AuditDecision(str, Enum):
    """Décisions d'audit."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    INFO = "INFO"
    ERROR = "ERROR"


class AuditService:
    """Service de journalisation des audits."""
    
    COLLECTION_AUDIT_LOGS = "audit_logs"
    COLLECTION_ESP32_DEVICES = "esp32_devices"
    
    def __init__(self):
        self.db = None
    
    def _get_db(self):
        """Lazy load database connection."""
        if self.db is None:
            self.db = get_db()
        return self.db
    
    def _mask_code(self, code: Optional[str]) -> str:
        """Masque un code d'accès pour le logging (ex: AB* ou **C)."""
        if not code:
            return "N/A"
        if len(code) <= 2:
            return "*" * len(code)
        return code[0] + "*" * (len(code) - 2) + code[-1]
    
    def _mask_phone(self, phone: Optional[str]) -> str:
        """Masque un numéro de téléphone (ex: ****1234)."""
        if not phone:
            return "N/A"
        if len(phone) <= 4:
            return "*" * len(phone)
        return "*" * (len(phone) - 4) + phone[-4:]
    
    async def log_event(
        self,
        event_type: AuditEventType,
        decision: AuditDecision,
        esp32_id: Optional[str] = None,
        code: Optional[str] = None,
        barrier_id: Optional[str] = None,
        user_id: Optional[str] = None,
        place_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """
        Enregistre un événement d'audit.
        
        Returns:
            ID du log créé
        """
        try:
            db = self._get_db()
            
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": event_type.value,
                "decision": decision.value,
                "esp32_id": esp32_id,
                "code_masked": self._mask_code(code),
                "barrier_id": barrier_id,
                "user_id": user_id,
                "place_id": place_id,
                "ip_address": ip_address,
                "details": details or {}
            }
            
            # Créer le document dans Firestore
            doc_ref = db.db.collection(self.COLLECTION_AUDIT_LOGS).document()
            doc_ref.set(log_entry)
            
            # Log aussi dans le fichier pour backup
            log_message = (
                f"AUDIT | {event_type.value} | {decision.value} | "
                f"ESP32: {esp32_id or 'N/A'} | Code: {self._mask_code(code)} | "
                f"Barrier: {barrier_id or 'N/A'}"
            )
            
            if decision == AuditDecision.DENY:
                logger.warning(log_message)
            elif decision == AuditDecision.ERROR:
                logger.error(log_message)
            else:
                logger.info(log_message)
            
            return doc_ref.id
            
        except Exception as e:
            logger.error(f"Erreur d'enregistrement audit: {e}")
            # Ne pas lever d'exception pour ne pas bloquer le flux principal
            return ""
    
    async def log_barrier_attempt(
        self,
        barrier_id: str,
        esp32_id: str,
        vehicle_presence: bool,
        code: Optional[str],
        code_valid: bool,
        access_granted: bool,
        reason: str,
        ip_address: Optional[str] = None
    ) -> str:
        """Log une tentative d'accès à la barrière."""
        event_type = AuditEventType.BARRIER_OPEN_SUCCESS if access_granted else AuditEventType.BARRIER_OPEN_DENIED
        decision = AuditDecision.ALLOW if access_granted else AuditDecision.DENY
        
        return await self.log_event(
            event_type=event_type,
            decision=decision,
            esp32_id=esp32_id,
            code=code,
            barrier_id=barrier_id,
            details={
                "vehicle_presence": vehicle_presence,
                "code_valid": code_valid,
                "reason": reason
            },
            ip_address=ip_address
        )
    
    async def log_code_validation(
        self,
        code: str,
        valid: bool,
        reason: str,
        esp32_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> str:
        """Log une tentative de validation de code."""
        if valid:
            event_type = AuditEventType.CODE_VALIDATION_SUCCESS
            decision = AuditDecision.ALLOW
        else:
            if "expired" in reason.lower():
                event_type = AuditEventType.CODE_EXPIRED
            elif "used" in reason.lower():
                event_type = AuditEventType.CODE_ALREADY_USED
            else:
                event_type = AuditEventType.CODE_VALIDATION_FAILED
            decision = AuditDecision.DENY
        
        return await self.log_event(
            event_type=event_type,
            decision=decision,
            esp32_id=esp32_id,
            code=code,
            user_id=user_id,
            details={"reason": reason}
        )
    
    async def log_sensor_event(
        self,
        esp32_id: str,
        place_id: str,
        new_state: str,
        old_state: Optional[str] = None,
        force_signal: Optional[int] = None,
        inconsistency: bool = False
    ) -> str:
        """Log un événement de capteur."""
        event_type = AuditEventType.SENSOR_INCONSISTENCY if inconsistency else AuditEventType.SENSOR_UPDATE
        decision = AuditDecision.ERROR if inconsistency else AuditDecision.INFO
        
        return await self.log_event(
            event_type=event_type,
            decision=decision,
            esp32_id=esp32_id,
            place_id=place_id,
            details={
                "new_state": new_state,
                "old_state": old_state,
                "force_signal": force_signal
            }
        )
    
    async def log_esp32_heartbeat(
        self,
        esp32_id: str,
        ip_address: str,
        firmware_version: Optional[str] = None,
        free_heap: Optional[int] = None,
        uptime_seconds: Optional[int] = None
    ) -> str:
        """Log un heartbeat ESP32 et met à jour le registre des appareils."""
        try:
            db = self._get_db()
            
            # Mettre à jour le registre des appareils ESP32
            device_data = {
                "esp32_id": esp32_id,
                "last_heartbeat": datetime.utcnow().isoformat(),
                "ip_address": ip_address,
                "firmware_version": firmware_version,
                "free_heap": free_heap,
                "uptime_seconds": uptime_seconds,
                "status": "online"
            }
            
            db.db.collection(self.COLLECTION_ESP32_DEVICES).document(esp32_id).set(
                device_data,
                merge=True
            )
            
            return await self.log_event(
                event_type=AuditEventType.ESP32_HEARTBEAT,
                decision=AuditDecision.INFO,
                esp32_id=esp32_id,
                ip_address=ip_address,
                details={
                    "firmware_version": firmware_version,
                    "free_heap": free_heap,
                    "uptime_seconds": uptime_seconds
                }
            )
            
        except Exception as e:
            logger.error(f"Erreur log heartbeat: {e}")
            return ""
    
    async def log_payment_event(
        self,
        payment_id: str,
        user_id: str,
        amount: float,
        status: str,
        provider: Optional[str] = None,
        phone_masked: Optional[str] = None
    ) -> str:
        """Log un événement de paiement."""
        if status == "success":
            event_type = AuditEventType.PAYMENT_SUCCESS
            decision = AuditDecision.ALLOW
        elif status == "refunded":
            event_type = AuditEventType.PAYMENT_REFUNDED
            decision = AuditDecision.INFO
        else:
            event_type = AuditEventType.PAYMENT_FAILED
            decision = AuditDecision.DENY
        
        return await self.log_event(
            event_type=event_type,
            decision=decision,
            user_id=user_id,
            details={
                "payment_id": payment_id,
                "amount": amount,
                "provider": provider,
                "phone_masked": phone_masked
            }
        )
    
    async def get_recent_logs(
        self,
        limit: int = 50,
        event_type: Optional[str] = None,
        decision: Optional[str] = None,
        esp32_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Récupère les logs récents avec filtres optionnels."""
        try:
            db = self._get_db()
            query = db.db.collection(self.COLLECTION_AUDIT_LOGS)
            
            # Appliquer les filtres
            if event_type:
                query = query.where("event_type", "==", event_type)
            if decision:
                query = query.where("decision", "==", decision)
            if esp32_id:
                query = query.where("esp32_id", "==", esp32_id)
            
            # Ordonner et limiter
            query = query.order_by("timestamp", direction="DESCENDING").limit(limit)
            
            docs = query.stream()
            logs = []
            for doc in docs:
                log_data = doc.to_dict()
                log_data["log_id"] = doc.id
                logs.append(log_data)
            
            return logs
            
        except Exception as e:
            logger.error(f"Erreur récupération logs: {e}")
            return []
    
    async def get_esp32_devices(self) -> List[Dict[str, Any]]:
        """Récupère la liste des appareils ESP32 enregistrés."""
        try:
            db = self._get_db()
            docs = db.db.collection(self.COLLECTION_ESP32_DEVICES).stream()
            
            devices = []
            for doc in docs:
                device_data = doc.to_dict()
                devices.append(device_data)
            
            return devices
            
        except Exception as e:
            logger.error(f"Erreur récupération devices: {e}")
            return []


# Singleton instance
_audit_service: Optional[AuditService] = None


def get_audit_service() -> AuditService:
    """Obtient l'instance singleton du service d'audit."""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service

# Export singleton instance for easy import
audit_service = get_audit_service()