"""
AeroPark Smart System - User Models
Defines all data models related to users and authentication.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """Enumeration of user roles."""
    USER = "user"
    ADMIN = "admin"
    SENSOR = "sensor"  # For ESP32 devices


class UserProfile(BaseModel):
    """User profile model returned from authentication."""
    uid: str = Field(..., description="Firebase user ID")
    email: Optional[EmailStr] = Field(default=None, description="User email address")
    display_name: Optional[str] = Field(default=None, description="User display name")
    photo_url: Optional[str] = Field(default=None, description="User profile photo URL")
    email_verified: bool = Field(default=False, description="Whether email is verified")
    role: UserRole = Field(default=UserRole.USER, description="User role")
    created_at: Optional[datetime] = Field(default=None, description="Account creation time")
    last_login: Optional[datetime] = Field(default=None, description="Last login timestamp")
    
    class Config:
        from_attributes = True


class UserReservationHistory(BaseModel):
    """Model for user's reservation history."""
    reservation_id: str
    spot_id: str
    spot_number: str
    zone: str
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    status: str  # completed, cancelled, expired
    actual_arrival: Optional[datetime] = None
    actual_departure: Optional[datetime] = None


class UserProfileResponse(BaseModel):
    """Complete user profile response with history."""
    profile: UserProfile
    active_reservation: Optional[dict] = None
    reservation_count: int = 0
    total_parking_hours: float = 0.0


class TokenPayload(BaseModel):
    """Decoded Firebase token payload."""
    uid: str
    email: Optional[str] = None
    email_verified: bool = False
    name: Optional[str] = None
    picture: Optional[str] = None
    auth_time: Optional[int] = None
    iat: Optional[int] = None
    exp: Optional[int] = None
    firebase: Optional[dict] = None
