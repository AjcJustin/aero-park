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
        Uses Firestore transaction to prevent race conditions.
        
        Args:
            request: Reservation request with spot_id and duration
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
                message="You already have an active reservation. Please release it first.",
                spot=self._dict_to_parking_spot(existing) if existing else None
            )
        
        try:
            # Create reservation with transaction
            result = await self.db.reserve_spot_transaction(
                spot_id=request.spot_id,
                user_id=user.uid,
                user_email=user.email or "unknown",
                duration_minutes=request.duration_minutes
            )
            
            spot_data = result["spot"]
            reservation_id = result["reservation_id"]
            
            spot = self._dict_to_parking_spot(spot_data)
            
            # Broadcast update to all clients
            await self._broadcast_reservation_update("reservation_created", spot)
            
            logger.info(
                f"Reservation created: spot={request.spot_id}, "
                f"user={user.uid}, duration={request.duration_minutes}min"
            )
            
            return ReservationResponse(
                success=True,
                message=f"Successfully reserved spot {spot.spot_number} for {request.duration_minutes} minutes",
                spot=spot,
                reservation_id=reservation_id,
                expires_at=spot.reservation_end_time
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
    
    async def get_user_reservation(self, user_id: str) -> Optional[ParkingSpot]:
        """
        Get user's current active reservation.
        
        Args:
            user_id: The user's ID
            
        Returns:
            Optional[ParkingSpot]: User's reserved/occupied spot
        """
        reservation = await self.db.get_user_active_reservation(user_id)
        if reservation:
            return self._dict_to_parking_spot(reservation)
        return None
    
    async def extend_reservation(
        self,
        spot_id: str,
        user_id: str,
        additional_minutes: int
    ) -> ReservationResponse:
        """
        Extend an existing reservation.
        
        Args:
            spot_id: ID of the reserved spot
            user_id: ID of the user
            additional_minutes: Minutes to add
            
        Returns:
            ReservationResponse: Extension confirmation
        """
        spot_data = await self.db.get_spot_by_id(spot_id)
        
        if not spot_data:
            return ReservationResponse(
                success=False,
                message="Parking spot not found"
            )
        
        if spot_data.get("reserved_by") != user_id:
            return ReservationResponse(
                success=False,
                message="You can only extend your own reservations"
            )
        
        current_end = spot_data.get("reservation_end_time")
        if not current_end:
            return ReservationResponse(
                success=False,
                message="No active reservation found"
            )
        
        # Convert if necessary
        if hasattr(current_end, "timestamp"):
            current_end = datetime.fromtimestamp(current_end.timestamp())
        
        new_end = current_end + timedelta(minutes=additional_minutes)
        new_duration = spot_data.get("reservation_duration_minutes", 0) + additional_minutes
        
        # Check max duration
        if new_duration > self.settings.max_reservation_duration_minutes:
            return ReservationResponse(
                success=False,
                message=f"Cannot exceed maximum duration of {self.settings.max_reservation_duration_minutes} minutes"
            )
        
        # Update the spot
        await self.db.update_spot(spot_id, {
            "reservation_end_time": new_end,
            "reservation_duration_minutes": new_duration
        })
        
        updated_spot = await self.db.get_spot_by_id(spot_id)
        spot = self._dict_to_parking_spot(updated_spot)
        
        # Broadcast update
        await self._broadcast_reservation_update("reservation_extended", spot)
        
        logger.info(f"Extended reservation for spot {spot_id} by {additional_minutes} minutes")
        
        return ReservationResponse(
            success=True,
            message=f"Reservation extended by {additional_minutes} minutes",
            spot=spot,
            expires_at=new_end
        )
    
    async def check_and_expire_reservations(self) -> int:
        """
        Check for expired reservations and release them.
        Called by the background scheduler.
        
        Returns:
            int: Number of expired reservations processed
        """
        try:
            expired = await self.db.get_expired_reservations()
            
            if not expired:
                return 0
            
            count = 0
            for spot_data in expired:
                spot_id = spot_data.get("id")
                
                # Only expire if still RESERVED (not OCCUPIED)
                if spot_data.get("status") == "RESERVED":
                    await self.db.release_spot(
                        spot_id,
                        reason="Reservation expired without vehicle arrival"
                    )
                    
                    # Broadcast expiry
                    await self._broadcast_reservation_update(
                        "reservation_expired",
                        {"spot_id": spot_id}
                    )
                    
                    count += 1
                    logger.info(f"Expired reservation for spot {spot_id}")
            
            return count
            
        except Exception as e:
            logger.error(f"Error checking expired reservations: {e}")
            return 0
    
    async def _broadcast_reservation_update(self, event_type: str, data: Any):
        """Broadcast reservation update to all WebSocket clients."""
        try:
            manager = get_websocket_manager()
            message = {
                "type": event_type,
                "data": data.model_dump() if hasattr(data, "model_dump") else data,
                "timestamp": datetime.utcnow().isoformat()
            }
            await manager.broadcast(message)
        except Exception as e:
            logger.error(f"Error broadcasting reservation update: {e}")
    
    def _dict_to_parking_spot(self, data: Dict[str, Any]) -> ParkingSpot:
        """Convert Firestore document to ParkingSpot model."""
        for field in ["reservation_start_time", "reservation_end_time",
                      "occupied_at", "created_at", "updated_at"]:
            if field in data and data[field]:
                if hasattr(data[field], "timestamp"):
                    data[field] = datetime.fromtimestamp(data[field].timestamp())
        
        return ParkingSpot(**data)


# Service instance
_reservation_service: Optional[ReservationService] = None


def get_reservation_service() -> ReservationService:
    """Get the ReservationService singleton instance."""
    global _reservation_service
    if _reservation_service is None:
        _reservation_service = ReservationService()
    return _reservation_service
