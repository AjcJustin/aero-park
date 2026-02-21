"""
AeroPark Smart System - Reservation Service
Handles all reservation operations and business logic.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from database.firebase_db import get_db, FirebaseDB
from models.parking import (
    ParkingSpot,
    ParkingSpotStatus,
    ReservationRequest,
    ReservationResponse,
)
from models.user import UserProfile
from services.websocket_service import get_websocket_manager
from config import get_settings

# Configure logging
logger = logging.getLogger(__name__)


class ReservationService:
    """
    Service class for reservation operations.
    Handles reservation creation, validation, and expiry.
    """
    
    def __init__(self, db: FirebaseDB = None):
        self.db = db or get_db()
        self.settings = get_settings()
    
    async def create_reservation(
        self,
        request: ReservationRequest,
        user: UserProfile
    ) -> ReservationResponse:
        """
        Create a new parking reservation.
        
        Args:
            request: Reservation request with place_id and duration
            user: Authenticated user making the reservation
            
        Returns:
            ReservationResponse: Reservation confirmation
        """
        # Validate duration limits
        if request.duration_minutes > self.settings.max_reservation_duration_minutes:
            return ReservationResponse(
                success=False,
                message=f"Maximum reservation duration is {self.settings.max_reservation_duration_minutes} minutes"
            )
        
        # Check if user already has an active reservation
        existing = await self.db.get_user_active_reservation(user.uid)
        if existing:
            return ReservationResponse(
                success=False,
                message="You already have an active reservation. Please release it first."
            )
        
        try:
            # Create reservation via DB
            result = await self.db.reserve_place(
                place_id=request.place_id,
                user_id=user.uid,
                user_email=user.email or "unknown",
                duration_minutes=request.duration_minutes
            )
            
            # Broadcast update to all clients
            try:
                manager = get_websocket_manager()
                await manager.notify_reservation(request.place_id, "create")
            except Exception as ws_err:
                logger.error(f"WS Notify error: {ws_err}")
            
            logger.info(
                f"Reservation created: place={request.place_id}, "
                f"user={user.uid}, duration={request.duration_minutes}min"
            )
            
            return ReservationResponse(
                success=True,
                message=f"Place {request.place_id} réservée avec succès",
                place_id=request.place_id,
                reservation_end=result.get("reservation_end_time")
            )
            
        except ValueError as e:
            logger.warning(f"Reservation failed: {e}")
            return ReservationResponse(
                success=False,
                message=str(e)
            )
        except Exception as e:
            logger.error(f"Reservation error: {e}")
            return ReservationResponse(
                success=False,
                message="An error occurred while processing your reservation"
            )
    
    async def get_user_reservation(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user's current active reservation.
        """
        return await self.db.get_user_active_reservation(user_id)
    
    async def extend_reservation(
        self,
        place_id: str,
        user_id: str,
        additional_minutes: int
    ) -> ReservationResponse:
        """
        Extend an existing reservation.
        """
        place_data = await self.db.get_place_by_id(place_id)
        
        if not place_data:
            return ReservationResponse(
                success=False,
                message="Parking place not found"
            )
        
        if place_data.get("reserved_by") != user_id:
            return ReservationResponse(
                success=False,
                message="You can only extend your own reservations"
            )
        
        current_end = place_data.get("reservation_end_time")
        if not current_end:
            return ReservationResponse(
                success=False,
                message="No active reservation found"
            )
        
        # Convert if necessary
        if hasattr(current_end, "timestamp"):
            # Firestore timestamp
            current_end_dt = datetime.fromtimestamp(current_end.timestamp())
        else:
            current_end_dt = current_end
        
        new_end = current_end_dt + timedelta(minutes=additional_minutes)
        new_duration = place_data.get("reservation_duration_minutes", 0) + additional_minutes
        
        # Check max duration
        if new_duration > self.settings.max_reservation_duration_minutes:
            return ReservationResponse(
                success=False,
                message=f"Cannot exceed maximum duration of {self.settings.max_reservation_duration_minutes} minutes"
            )
        
        # Update the place in DB
        await self.db.db.collection(self.db.COLLECTION_PLACES).document(place_id).update({
            "reservation_end_time": new_end,
            "reservation_duration_minutes": new_duration,
            "last_update": datetime.utcnow()
        })
        
        # Broadcast update
        try:
            manager = get_websocket_manager()
            await manager.notify_reservation(place_id, "update")
        except Exception as ws_err:
            logger.error(f"WS Notify error: {ws_err}")
            
        logger.info(f"Extended reservation for place {place_id} by {additional_minutes} minutes")
        
        return ReservationResponse(
            success=True,
            message=f"Reservation extended by {additional_minutes} minutes",
            place_id=place_id,
            reservation_end=new_end
        )
    
    async def check_and_expire_reservations(self) -> int:
        """
        Check for expired reservations and release them.
        Called by the background scheduler.
        """
        try:
            expired = await self.db.get_expired_reservations()
            
            if not expired:
                return 0
            
            count = 0
            for place_data in expired:
                place_id = place_data.get("place_id")
                
                # Only expire if still reserved (not occupied)
                if place_data.get("etat") == "reserved":
                    await self.db.release_place(place_id)
                    
                    # Broadcast update via WebSocket
                    try:
                        manager = get_websocket_manager()
                        await manager.notify_reservation(place_id, "cancel")
                    except Exception as ws_err:
                        logger.error(f"Error broadcasting expiry for {place_id}: {ws_err}")
                    
                    count += 1
                    logger.info(f"Expired reservation for place {place_id}")
            
            return count
            
        except Exception as e:
            logger.error(f"Error checking expired reservations: {e}")
            return 0


# Service instance
_reservation_service: Optional[ReservationService] = None


def get_reservation_service() -> ReservationService:
    """Get the ReservationService singleton instance."""
    global _reservation_service
    if _reservation_service is None:
        _reservation_service = ReservationService()
    return _reservation_service
