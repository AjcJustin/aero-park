"""
AeroPark Smart System - Parking Router
Handles parking status, reservations, and releases.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import logging

from models.parking import (
    ParkingSpot,
    ParkingStatusResponse,
    ReservationRequest,
    ReservationResponse,
    ReleaseRequest,
)
from models.user import UserProfile
from security.firebase_auth import get_current_user
from services.parking_service import get_parking_service
from services.reservation_service import get_reservation_service

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/parking",
    tags=["Parking"],
    responses={401: {"description": "Unauthorized"}}
)


@router.get(
    "/status",
    response_model=ParkingStatusResponse,
    summary="Get Parking Status",
    description="Returns current status of all parking spots including availability counts."
)
async def get_parking_status() -> ParkingStatusResponse:
    """
    Get the current status of all parking spots.
    
    This endpoint is public and returns:
    - Total number of spots
    - Count of available, reserved, and occupied spots
    - Full list of all spots with their current status
    
    No authentication required for viewing parking status.
    """
    try:
        service = get_parking_service()
        return await service.get_parking_status()
        
    except Exception as e:
        logger.error(f"Error fetching parking status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching parking status"
        )


@router.get(
    "/available",
    response_model=List[ParkingSpot],
    summary="Get Available Spots",
    description="Returns only parking spots that are currently available for reservation."
)
async def get_available_spots() -> List[ParkingSpot]:
    """
    Get all available parking spots.
    
    Returns only spots with status AVAILABLE.
    Useful for showing reservation options to users.
    """
    try:
        service = get_parking_service()
        return await service.get_available_spots()
        
    except Exception as e:
        logger.error(f"Error fetching available spots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching available spots"
        )


@router.get(
    "/spot/{spot_id}",
    response_model=ParkingSpot,
    summary="Get Spot Details",
    description="Returns detailed information about a specific parking spot."
)
async def get_spot_details(spot_id: str) -> ParkingSpot:
    """
    Get details of a specific parking spot.
    
    Args:
        spot_id: The parking spot ID
        
    Returns:
        ParkingSpot: Full spot details
    """
    try:
        service = get_parking_service()
        spot = await service.get_spot_by_id(spot_id)
        
        if not spot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parking spot {spot_id} not found"
            )
        
        return spot
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching spot {spot_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching spot details"
        )


@router.post(
    "/reserve",
    response_model=ReservationResponse,
    summary="Reserve Parking Spot",
    description="Reserve an available parking spot for a specified duration."
)
async def reserve_spot(
    request: ReservationRequest,
    user: UserProfile = Depends(get_current_user)
) -> ReservationResponse:
    """
    Reserve a parking spot.
    
    Authenticated users can reserve an available spot for a specified
    duration (15 minutes to 8 hours). The reservation uses a Firestore
    transaction to prevent race conditions when multiple users try to
    reserve the same spot simultaneously.
    
    Args:
        request: Reservation request with spot_id and duration
        user: Authenticated user making the reservation
        
    Returns:
        ReservationResponse: Reservation confirmation or error
    """
    try:
        service = get_reservation_service()
        result = await service.create_reservation(request, user)
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.message
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating reservation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing reservation"
        )


@router.post(
    "/release",
    summary="Release Parking Spot",
    description="Manually release a reserved or occupied parking spot."
)
async def release_spot(
    request: ReleaseRequest,
    user: UserProfile = Depends(get_current_user)
):
    """
    Release a parking spot.
    
    Allows users to manually release their reserved or occupied spot.
    Users can only release spots that they have reserved.
    
    Args:
        request: Release request with spot_id
        user: Authenticated user
        
    Returns:
        Success confirmation
    """
    try:
        service = get_parking_service()
        await service.release_spot(
            spot_id=request.spot_id,
            user_id=user.uid,
            reason=request.reason or "User requested release"
        )
        
        return {
            "success": True,
            "message": "Parking spot released successfully"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error releasing spot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error releasing parking spot"
        )


@router.post(
    "/extend",
    response_model=ReservationResponse,
    summary="Extend Reservation",
    description="Extend an existing parking reservation."
)
async def extend_reservation(
    spot_id: str,
    additional_minutes: int,
    user: UserProfile = Depends(get_current_user)
) -> ReservationResponse:
    """
    Extend a parking reservation.
    
    Allows users to add time to their existing reservation.
    Maximum total duration is 8 hours.
    
    Args:
        spot_id: The parking spot ID
        additional_minutes: Minutes to add (must be positive)
        user: Authenticated user
        
    Returns:
        ReservationResponse: Updated reservation details
    """
    if additional_minutes <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Additional minutes must be positive"
        )
    
    try:
        service = get_reservation_service()
        result = await service.extend_reservation(
            spot_id=spot_id,
            user_id=user.uid,
            additional_minutes=additional_minutes
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.message
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extending reservation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error extending reservation"
        )
