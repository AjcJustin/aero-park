"""
AeroPark Smart System - Parking Service
Handles all parking spot operations and business logic.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from database.firebase_db import get_db, FirebaseDB
from models.parking import (
    ParkingSpot,
    ParkingSpotStatus,
    ParkingSpotCreate,
    ParkingStatusResponse,
    SensorUpdateResponse,
)
from services.websocket_service import get_websocket_manager

# Configure logging
logger = logging.getLogger(__name__)


class ParkingService:
    """
    Service class for parking spot operations.
    Encapsulates business logic for parking management.
    """
    
    def __init__(self, db: FirebaseDB = None):
        self.db = db or get_db()
    
    async def get_all_spots(self) -> List[ParkingSpot]:
        """
        Get all parking spots with their current status.
        
        Returns:
            List[ParkingSpot]: All parking spots
        """
        spots_data = await self.db.get_all_spots()
        return [self._dict_to_parking_spot(spot) for spot in spots_data]
    
    async def get_parking_status(self) -> ParkingStatusResponse:
        """
        Get overview of parking status including counts.
        
        Returns:
            ParkingStatusResponse: Complete parking status overview
        """
        spots = await self.get_all_spots()
        
        available = sum(1 for s in spots if s.status == ParkingSpotStatus.AVAILABLE)
        reserved = sum(1 for s in spots if s.status == ParkingSpotStatus.RESERVED)
        occupied = sum(1 for s in spots if s.status == ParkingSpotStatus.OCCUPIED)
        
        return ParkingStatusResponse(
            total_spots=len(spots),
            available=available,
            reserved=reserved,
            occupied=occupied,
            spots=spots,
            timestamp=datetime.utcnow()
        )
    
    async def get_spot_by_id(self, spot_id: str) -> Optional[ParkingSpot]:
        """
        Get a single parking spot by ID.
        
        Args:
            spot_id: The parking spot ID
            
        Returns:
            Optional[ParkingSpot]: The parking spot or None
        """
        spot_data = await self.db.get_spot_by_id(spot_id)
        if spot_data:
            return self._dict_to_parking_spot(spot_data)
        return None
    
    async def get_available_spots(self) -> List[ParkingSpot]:
        """
        Get only available parking spots.
        
        Returns:
            List[ParkingSpot]: Available parking spots
        """
        all_spots = await self.get_all_spots()
        return [s for s in all_spots if s.status == ParkingSpotStatus.AVAILABLE]
    
    async def create_spot(self, spot_create: ParkingSpotCreate) -> ParkingSpot:
        """
        Create a new parking spot (admin only).
        
        Args:
            spot_create: Parking spot creation data
            
        Returns:
            ParkingSpot: Created parking spot
        """
        spot_data = spot_create.model_dump()
        spot_id = await self.db.create_spot(spot_data)
        
        # Fetch the created spot
        created_spot = await self.get_spot_by_id(spot_id)
        
        # Broadcast update
        await self._broadcast_parking_update("spot_created", created_spot)
        
        logger.info(f"Created new parking spot: {spot_id}")
        return created_spot
    
    async def delete_spot(self, spot_id: str) -> bool:
        """
        Delete a parking spot (admin only).
        
        Args:
            spot_id: ID of the spot to delete
            
        Returns:
            bool: True if deleted successfully
            
        Raises:
            ValueError: If spot is occupied or reserved
        """
        spot = await self.get_spot_by_id(spot_id)
        
        if not spot:
            raise ValueError(f"Parking spot {spot_id} not found")
        
        if spot.status != ParkingSpotStatus.AVAILABLE:
            raise ValueError(
                f"Cannot delete spot with status {spot.status}. "
                "Release the spot first."
            )
        
        await self.db.delete_spot(spot_id)
        
        # Broadcast update
        await self._broadcast_parking_update("spot_deleted", {"id": spot_id})
        
        logger.info(f"Deleted parking spot: {spot_id}")
        return True
    
    async def update_from_sensor(
        self,
        spot_id: str,
        is_occupied: bool,
        sensor_id: Optional[str] = None
    ) -> SensorUpdateResponse:
        """
        Update parking spot status from ESP32 sensor data.
        
        Args:
            spot_id: ID of the parking spot
            is_occupied: Whether a vehicle is detected
            sensor_id: ID of the reporting sensor
            
        Returns:
            SensorUpdateResponse: Update confirmation
        """
        result = await self.db.update_spot_from_sensor(
            spot_id=spot_id,
            is_occupied=is_occupied,
            sensor_id=sensor_id
        )
        
        # Get updated spot
        updated_spot = await self.get_spot_by_id(spot_id)
        
        # Broadcast if there was a state transition
        if result.get("transition"):
            await self._broadcast_parking_update(
                "sensor_update",
                {
                    "spot": updated_spot.model_dump() if updated_spot else None,
                    "transition": result.get("transition")
                }
            )
        
        new_status = ParkingSpotStatus(result.get("status", "AVAILABLE"))
        
        return SensorUpdateResponse(
            success=True,
            message=f"Spot updated: {result.get('transition') or 'No change'}",
            spot_id=spot_id,
            new_status=new_status,
            timestamp=datetime.utcnow()
        )
    
    async def release_spot(self, spot_id: str, user_id: str, reason: str = None) -> bool:
        """
        Manually release a parking spot.
        
        Args:
            spot_id: ID of the spot to release
            user_id: ID of the user requesting release
            reason: Optional reason for release
            
        Returns:
            bool: True if released successfully
            
        Raises:
            ValueError: If user doesn't own the reservation
        """
        spot = await self.get_spot_by_id(spot_id)
        
        if not spot:
            raise ValueError(f"Parking spot {spot_id} not found")
        
        if spot.status == ParkingSpotStatus.AVAILABLE:
            raise ValueError("Spot is already available")
        
        # Check if user owns this reservation (or is admin - handled in router)
        if spot.reserved_by and spot.reserved_by != user_id:
            raise ValueError("You can only release your own reservations")
        
        await self.db.release_spot(spot_id, reason)
        
        # Get updated spot and broadcast
        updated_spot = await self.get_spot_by_id(spot_id)
        await self._broadcast_parking_update("spot_released", updated_spot)
        
        logger.info(f"Released spot {spot_id} by user {user_id}")
        return True
    
    async def _broadcast_parking_update(self, event_type: str, data: Any):
        """Broadcast parking update to all WebSocket clients."""
        try:
            manager = get_websocket_manager()
            message = {
                "type": event_type,
                "data": data.model_dump() if hasattr(data, "model_dump") else data,
                "timestamp": datetime.utcnow().isoformat()
            }
            await manager.broadcast(message)
        except Exception as e:
            logger.error(f"Error broadcasting update: {e}")
    
    def _dict_to_parking_spot(self, data: Dict[str, Any]) -> ParkingSpot:
        """Convert Firestore document to ParkingSpot model."""
        # Handle datetime conversions
        for field in ["reservation_start_time", "reservation_end_time", 
                      "occupied_at", "created_at", "updated_at"]:
            if field in data and data[field]:
                if hasattr(data[field], "timestamp"):
                    # Firestore Timestamp object
                    data[field] = data[field].timestamp()
                    data[field] = datetime.fromtimestamp(data[field])
        
        return ParkingSpot(**data)


# Service instance
_parking_service: Optional[ParkingService] = None


def get_parking_service() -> ParkingService:
    """Get the ParkingService singleton instance."""
    global _parking_service
    if _parking_service is None:
        _parking_service = ParkingService()
    return _parking_service
