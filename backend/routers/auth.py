"""
AeroPark Smart System - Authentication Router
Handles user authentication and profile endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
import logging

from models.user import UserProfile, UserProfileResponse
from security.firebase_auth import get_current_user
from database.firebase_db import get_db

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/users",
    tags=["Authentication"],
    responses={401: {"description": "Unauthorized"}}
)


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get Current User Profile",
    description="Returns the authenticated user's profile and active reservation."
)
async def get_my_profile(
    user: UserProfile = Depends(get_current_user)
) -> UserProfileResponse:
    """
    Get the current authenticated user's profile.
    
    Returns user profile information from Firebase Auth and Firestore,
    including any active reservation.
    """
    try:
        db = get_db()
        
        # Get active reservation if any
        active_reservation = await db.get_user_active_reservation(user.uid)
        
        # Get user stats (simplified - could be expanded)
        user_data = await db.get_user_profile(user.uid)
        reservation_count = user_data.get("reservation_count", 0) if user_data else 0
        total_hours = user_data.get("total_parking_hours", 0.0) if user_data else 0.0
        
        return UserProfileResponse(
            profile=user,
            active_reservation=active_reservation,
            reservation_count=reservation_count,
            total_parking_hours=total_hours
        )
        
    except Exception as e:
        logger.error(f"Error fetching user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching user profile"
        )


@router.get(
    "/me/reservation",
    summary="Get Current User's Active Reservation",
    description="Returns the user's current active parking reservation if any."
)
async def get_my_reservation(
    user: UserProfile = Depends(get_current_user)
):
    """
    Get the current user's active reservation.
    
    Returns the parking spot that is currently reserved or occupied
    by the authenticated user, or null if no active reservation.
    """
    try:
        db = get_db()
        reservation = await db.get_user_active_reservation(user.uid)
        
        if reservation:
            return {
                "has_reservation": True,
                "reservation": reservation
            }
        
        return {
            "has_reservation": False,
            "reservation": None
        }
        
    except Exception as e:
        logger.error(f"Error fetching user reservation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching reservation"
        )


@router.put(
    "/me/profile",
    summary="Update User Profile",
    description="Update the current user's profile information."
)
async def update_my_profile(
    display_name: Optional[str] = None,
    vehicle_plate: Optional[str] = None,
    user: UserProfile = Depends(get_current_user)
):
    """
    Update the current user's profile.
    
    Allows updating optional profile fields like display name
    and default vehicle plate.
    """
    try:
        db = get_db()
        
        updates = {}
        if display_name:
            updates["display_name"] = display_name
        if vehicle_plate:
            updates["vehicle_plate"] = vehicle_plate
        
        if updates:
            await db.upsert_user_profile(user.uid, updates)
        
        return {
            "success": True,
            "message": "Profile updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating profile"
        )
