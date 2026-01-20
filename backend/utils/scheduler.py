"""
AeroPark Smart System - Background Scheduler
Handles background tasks like reservation expiry checking.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import Optional
import logging
import asyncio

# Configure logging
logger = logging.getLogger(__name__)


class ReservationScheduler:
    """
    Background scheduler for periodic tasks.
    Primarily handles reservation expiry checks.
    """
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._is_running = False
    
    def start(self):
        """Start the background scheduler."""
        if self._is_running:
            logger.warning("Scheduler is already running")
            return
        
        # Add reservation expiry check job
        self.scheduler.add_job(
            self._check_expired_reservations,
            trigger=IntervalTrigger(seconds=30),  # Check every 30 seconds
            id="check_expired_reservations",
            name="Check and expire overdue reservations",
            replace_existing=True
        )
        
        # Add access code expiration job
        self.scheduler.add_job(
            self._cleanup_expired_access_codes,
            trigger=IntervalTrigger(minutes=1),  # Check every minute
            id="cleanup_expired_codes",
            name="Cleanup expired access codes and free spots",
            replace_existing=True
        )
        
        # Add periodic status broadcast job
        self.scheduler.add_job(
            self._broadcast_status,
            trigger=IntervalTrigger(minutes=1),  # Broadcast every minute
            id="broadcast_parking_status",
            name="Broadcast parking status updates",
            replace_existing=True
        )
        
        self.scheduler.start()
        self._is_running = True
        logger.info("Background scheduler started")
    
    def stop(self):
        """Stop the background scheduler."""
        if not self._is_running:
            return
        
        self.scheduler.shutdown(wait=False)
        self._is_running = False
        logger.info("Background scheduler stopped")
    
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._is_running
    
    async def _check_expired_reservations(self):
        """
        Check for and handle expired reservations.
        This runs periodically as a background task.
        """
        try:
            # Import here to avoid circular imports
            from services.reservation_service import get_reservation_service
            
            service = get_reservation_service()
            expired_count = await service.check_and_expire_reservations()
            
            if expired_count > 0:
                logger.info(f"Processed {expired_count} expired reservation(s)")
                
        except Exception as e:
            logger.error(f"Error checking expired reservations: {e}")
    
    async def _broadcast_status(self):
        """
        Periodically broadcast parking status to all WebSocket clients.
        Keeps clients in sync even without explicit updates.
        """
        try:
            # Import here to avoid circular imports
            from services.websocket_service import get_websocket_manager
            from database.firebase_db import get_db
            
            db = get_db()
            manager = get_websocket_manager()
            
            if manager.get_connection_count() > 0:
                places = await db.get_all_places()
                total = len(places)
                free = sum(1 for p in places if p.get("etat") == "free")
                occupied = sum(1 for p in places if p.get("etat") == "occupied")
                reserved = sum(1 for p in places if p.get("etat") == "reserved")
                
                status = {
                    "type": "status_update",
                    "total_places": total,
                    "libres": free,
                    "occupees": occupied,
                    "reservees": reserved,
                    "places": places
                }
                await manager.broadcast_parking_status(status)
                
        except Exception as e:
            logger.error(f"Error broadcasting status: {e}")
    
    async def _cleanup_expired_access_codes(self):
        """
        Background job to cleanup expired access codes.
        
        This job runs every minute and:
        1. Finds all expired access codes (past expiry_time)
        2. Marks codes as EXPIRED
        3. Frees up associated parking spots
        4. Cancels reservations if not yet used
        5. Logs audit events for each expiration
        """
        try:
            from services.access_code_service import access_code_service
            from services.audit_service import audit_service, AuditEventType, AuditDecision
            from database.firebase_db import get_db
            from datetime import datetime, timezone
            
            db = get_db()
            
            # Get all access codes
            codes_ref = db.db.collection("access_codes")
            all_codes = codes_ref.stream()
            
            expired_count = 0
            now = datetime.now(timezone.utc)
            
            for code_doc in all_codes:
                code_data = code_doc.to_dict()
                code_id = code_doc.id
                
                # Check if code is active and expired
                if code_data.get("status") not in ["ACTIVE", "active"]:
                    continue
                
                expiry_time = code_data.get("expiry_time")
                if not expiry_time:
                    continue
                
                # Handle different datetime formats
                if hasattr(expiry_time, 'timestamp'):
                    expiry_dt = expiry_time
                else:
                    continue
                
                # Make expiry_dt timezone aware if needed
                if expiry_dt.tzinfo is None:
                    expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
                
                # Check if expired
                if now > expiry_dt:
                    # Mark code as expired
                    codes_ref.document(code_id).update({
                        "status": "EXPIRED",
                        "expired_at": now
                    })
                    
                    # Free the parking spot if reservation exists
                    reservation_id = code_data.get("reservation_id")
                    if reservation_id:
                        reservation = await db.get_reservation(reservation_id)
                        if reservation:
                            spot_id = reservation.get("spot_id")
                            if spot_id:
                                await db.update_place_status(spot_id, "free")
                            
                            # Update reservation status
                            await db.update_reservation(reservation_id, {
                                "status": "EXPIRED",
                                "expired_at": now.isoformat()
                            })
                    
                    # Log audit event
                    await audit_service.log_event(
                        event_type=AuditEventType.CODE_EXPIRED,
                        decision=AuditDecision.INFO,
                        barrier_id="scheduler",
                        details={
                            "code_id": code_id,
                            "code": code_data.get("code", "")[:2] + "***",
                            "reservation_id": reservation_id,
                            "expired_at": now.isoformat(),
                            "reason": "Automatic expiration by scheduler"
                        }
                    )
                    
                    expired_count += 1
            
            if expired_count > 0:
                logger.info(f"Expired {expired_count} access codes")
                
        except Exception as e:
            logger.error(f"Error cleaning up expired access codes: {e}")
    
    def add_reservation_reminder(self, reservation_id: str, spot_id: str, 
                                  user_id: str, reminder_time_seconds: int):
        """
        Add a one-time reminder job for a reservation.
        Can be used to notify users before expiry.
        
        Args:
            reservation_id: The reservation ID
            spot_id: The parking spot ID
            user_id: The user ID
            reminder_time_seconds: Seconds from now to send reminder
        """
        from datetime import datetime, timedelta
        
        run_time = datetime.utcnow() + timedelta(seconds=reminder_time_seconds)
        
        self.scheduler.add_job(
            self._send_expiry_reminder,
            trigger="date",
            run_date=run_time,
            args=[reservation_id, spot_id, user_id],
            id=f"reminder_{reservation_id}",
            name=f"Expiry reminder for reservation {reservation_id}",
            replace_existing=True
        )
        
        logger.info(f"Added reminder for reservation {reservation_id} at {run_time}")
    
    async def _send_expiry_reminder(self, reservation_id: str, spot_id: str, user_id: str):
        """
        Send a reminder to user about upcoming reservation expiry.
        
        Args:
            reservation_id: The reservation ID
            spot_id: The parking spot ID
            user_id: The user ID
        """
        try:
            from services.websocket_service import get_websocket_manager
            
            manager = get_websocket_manager()
            await manager.broadcast({
                "type": "reservation_reminder",
                "data": {
                    "reservation_id": reservation_id,
                    "spot_id": spot_id,
                    "user_id": user_id,
                    "message": "Your reservation will expire in 5 minutes"
                }
            })
            
            logger.info(f"Sent expiry reminder for reservation {reservation_id}")
            
        except Exception as e:
            logger.error(f"Error sending reminder: {e}")
    
    def cancel_reminder(self, reservation_id: str):
        """
        Cancel a scheduled reminder.
        
        Args:
            reservation_id: The reservation ID
        """
        job_id = f"reminder_{reservation_id}"
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Cancelled reminder for reservation {reservation_id}")
        except Exception:
            pass  # Job might not exist


# Singleton instance
_scheduler_instance: Optional[ReservationScheduler] = None


def get_scheduler() -> ReservationScheduler:
    """Get the scheduler singleton instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = ReservationScheduler()
    return _scheduler_instance


def start_scheduler():
    """Start the background scheduler."""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler():
    """Stop the background scheduler."""
    scheduler = get_scheduler()
    scheduler.stop()
