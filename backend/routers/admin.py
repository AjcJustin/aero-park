"""
AeroPark Smart System - Admin Router
Handles administrative operations for parking management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
import logging

from models.parking import (
    ParkingSpot,
    ParkingSpotCreate,
    ParkingSpotUpdate,
    ParkingStatusResponse,
)
from models.user import UserProfile
from security.firebase_auth import get_current_admin
from security.api_key import verify_admin_api_key
from services.parking_service import get_parking_service
from database.firebase_db import get_db

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/admin/parking",
    tags=["Admin"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - Admin access required"}
    }
)


@router.get(
    "/all",
    response_model=List[ParkingSpot],
    summary="Get All Parking Spots (Admin)",
    description="Returns all parking spots with full details. Admin access required."
)
async def get_all_spots(
    admin: UserProfile = Depends(get_current_admin)
) -> List[ParkingSpot]:
    """
    Get all parking spots with full administrative details.
    
    Requires admin authentication.
    Returns complete spot information including reservation details.
    """
    try:
        service = get_parking_service()
        return await service.get_all_spots()
        
    except Exception as e:
        logger.error(f"Admin error fetching spots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching parking spots"
        )


@router.get(
    "/stats",
    summary="Get Parking Statistics (Admin)",
    description="Returns detailed statistics about parking usage."
)
async def get_parking_stats(
    admin: UserProfile = Depends(get_current_admin)
):
    """
    Get detailed parking statistics.
    
    Returns:
    - Spot counts by status
    - Reservation metrics
    - Occupancy rates
    """
    try:
        service = get_parking_service()
        status_response = await service.get_parking_status()
        
        total = status_response.total_spots
        occupied = status_response.occupied
        reserved = status_response.reserved
        
        occupancy_rate = ((occupied + reserved) / total * 100) if total > 0 else 0
        
        return {
            "total_spots": total,
            "available": status_response.available,
            "reserved": reserved,
            "occupied": occupied,
            "occupancy_rate": round(occupancy_rate, 2),
            "timestamp": status_response.timestamp
        }
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching statistics"
        )


@router.post(
    "/add",
    response_model=ParkingSpot,
    status_code=status.HTTP_201_CREATED,
    summary="Add Parking Spot (Admin)",
    description="Add a new parking spot to the system."
)
async def add_parking_spot(
    spot: ParkingSpotCreate,
    admin: UserProfile = Depends(get_current_admin)
) -> ParkingSpot:
    """
    Add a new parking spot.
    
    Creates a new parking spot with the specified configuration.
    Requires admin authentication.
    
    Args:
        spot: Parking spot creation data
        
    Returns:
        ParkingSpot: The created parking spot
    """
    try:
        service = get_parking_service()
        created_spot = await service.create_spot(spot)
        
        logger.info(f"Admin {admin.uid} created spot {created_spot.id}")
        return created_spot
        
    except Exception as e:
        logger.error(f"Error creating spot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating parking spot"
        )


@router.put(
    "/{spot_id}",
    response_model=ParkingSpot,
    summary="Update Parking Spot (Admin)",
    description="Update an existing parking spot's configuration."
)
async def update_parking_spot(
    spot_id: str,
    updates: ParkingSpotUpdate,
    admin: UserProfile = Depends(get_current_admin)
) -> ParkingSpot:
    """
    Update a parking spot.
    
    Updates spot configuration (number, zone, floor, sensor_id).
    Cannot change status or reservation info through this endpoint.
    
    Args:
        spot_id: The parking spot ID
        updates: Fields to update
        
    Returns:
        ParkingSpot: The updated parking spot
    """
    try:
        db = get_db()
        service = get_parking_service()
        
        # Check spot exists
        existing = await service.get_spot_by_id(spot_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parking spot {spot_id} not found"
            )
        
        # Apply updates
        update_data = updates.model_dump(exclude_unset=True)
        if update_data:
            await db.update_spot(spot_id, update_data)
        
        # Return updated spot
        updated = await service.get_spot_by_id(spot_id)
        
        logger.info(f"Admin {admin.uid} updated spot {spot_id}")
        return updated
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating spot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating parking spot"
        )


@router.delete(
    "/{spot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Parking Spot (Admin)",
    description="Remove a parking spot from the system."
)
async def delete_parking_spot(
    spot_id: str,
    admin: UserProfile = Depends(get_current_admin)
):
    """
    Delete a parking spot.
    
    Removes a parking spot from the system.
    Cannot delete spots that are currently reserved or occupied.
    
    Args:
        spot_id: The parking spot ID to delete
    """
    try:
        service = get_parking_service()
        await service.delete_spot(spot_id)
        
        logger.info(f"Admin {admin.uid} deleted spot {spot_id}")
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting spot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting parking spot"
        )


@router.post(
    "/force-release/{spot_id}",
    summary="Force Release Spot (Admin)",
    description="Force release any parking spot regardless of reservation."
)
async def force_release_spot(
    spot_id: str,
    reason: Optional[str] = None,
    admin: UserProfile = Depends(get_current_admin)
):
    """
    Force release a parking spot.
    
    Allows admins to release any spot regardless of who reserved it.
    Useful for emergency situations or maintenance.
    
    Args:
        spot_id: The parking spot ID
        reason: Optional reason for force release
    """
    try:
        db = get_db()
        service = get_parking_service()
        
        spot = await service.get_spot_by_id(spot_id)
        if not spot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parking spot {spot_id} not found"
            )
        
        await db.release_spot(
            spot_id,
            reason=f"Admin force release: {reason or 'No reason provided'}"
        )
        
        logger.warning(f"Admin {admin.uid} force released spot {spot_id}: {reason}")
        
        return {
            "success": True,
            "message": "Parking spot force released"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error force releasing spot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error force releasing spot"
        )


@router.post(
    "/initialize",
    summary="Initialize Default Spots (Admin)",
    description="Initialize the system with default parking spots."
)
async def initialize_spots(
    count: int = 5,
    admin: UserProfile = Depends(get_current_admin)
):
    """
    Initialize default parking spots.
    
    Creates initial parking spots if none exist.
    Will not create spots if spots already exist.
    
    Args:
        count: Number of spots to create (default 5)
    """
    try:
        db = get_db()
        created_ids = await db.initialize_default_spots(count)
        
        if created_ids:
            logger.info(f"Admin {admin.uid} initialized {len(created_ids)} spots")
            return {
                "success": True,
                "message": f"Created {len(created_ids)} parking spots",
                "spot_ids": created_ids
            }
        else:
            return {
                "success": True,
                "message": "Spots already exist, no new spots created",
                "spot_ids": []
            }
        
    except Exception as e:
        logger.error(f"Error initializing spots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error initializing parking spots"
        )
