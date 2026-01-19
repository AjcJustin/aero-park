"""
AeroPark Smart System - Parking Models
Defines all data models related to parking spots and reservations.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ParkingSpotStatus(str, Enum):
    """Enumeration of possible parking spot states."""
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    OCCUPIED = "OCCUPIED"


class ParkingSpotBase(BaseModel):
    """Base model for parking spot data."""
    spot_number: str = Field(
        ...,
        description="Human-readable spot identifier (e.g., A1, B2)",
        min_length=1,
        max_length=10
    )
    zone: Optional[str] = Field(
        default="General",
        description="Parking zone (e.g., Terminal 1, VIP, Economy)"
    )
    floor: Optional[int] = Field(
        default=1,
        description="Floor level of the parking spot"
    )
    sensor_id: Optional[str] = Field(
        default=None,
        description="Associated ESP32 sensor ID"
    )


class ParkingSpot(ParkingSpotBase):
    """Complete parking spot model with all fields."""
    id: str = Field(..., description="Unique identifier for the parking spot")
    status: ParkingSpotStatus = Field(
        default=ParkingSpotStatus.AVAILABLE,
        description="Current status of the parking spot"
    )
    reserved_by: Optional[str] = Field(
        default=None,
        description="User ID of the person who reserved the spot"
    )
    reserved_by_email: Optional[str] = Field(
        default=None,
        description="Email of the person who reserved the spot"
    )
    reservation_start_time: Optional[datetime] = Field(
        default=None,
        description="When the reservation started"
    )
    reservation_end_time: Optional[datetime] = Field(
        default=None,
        description="When the reservation is set to expire"
    )
    reservation_duration_minutes: Optional[int] = Field(
        default=None,
        description="Duration of the reservation in minutes"
    )
    occupied_at: Optional[datetime] = Field(
        default=None,
        description="When the vehicle actually arrived"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the spot was added to the system"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ParkingSpotCreate(ParkingSpotBase):
    """Model for creating a new parking spot (admin only)."""
    pass


class ParkingSpotUpdate(BaseModel):
    """Model for updating parking spot details."""
    spot_number: Optional[str] = Field(default=None, min_length=1, max_length=10)
    zone: Optional[str] = None
    floor: Optional[int] = None
    sensor_id: Optional[str] = None


class ReservationRequest(BaseModel):
    """Request model for reserving a parking spot."""
    spot_id: str = Field(
        ...,
        description="ID of the spot to reserve"
    )
    duration_minutes: int = Field(
        ...,
        ge=15,
        le=480,
        description="Reservation duration in minutes (15 min to 8 hours)"
    )
    vehicle_plate: Optional[str] = Field(
        default=None,
        description="Optional vehicle license plate for verification"
    )
    
    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        """Ensure duration is in 15-minute increments."""
        if v % 15 != 0:
            # Round up to nearest 15 minutes
            v = ((v // 15) + 1) * 15
        return v


class ReservationResponse(BaseModel):
    """Response model after successful reservation."""
    success: bool
    message: str
    spot: Optional[ParkingSpot] = None
    reservation_id: Optional[str] = None
    expires_at: Optional[datetime] = None


class SensorUpdateRequest(BaseModel):
    """Request model for ESP32 sensor status updates."""
    spot_id: str = Field(
        ...,
        description="ID of the parking spot being monitored"
    )
    status: str = Field(
        ...,
        description="Sensor detected status: 'occupied' or 'free'"
    )
    sensor_id: Optional[str] = Field(
        default=None,
        description="Identifier of the ESP32 sensor"
    )
    distance_cm: Optional[float] = Field(
        default=None,
        description="Distance reading from ultrasonic sensor in cm"
    )
    
    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Normalize and validate status value."""
        v = v.lower().strip()
        if v not in ["occupied", "free"]:
            raise ValueError("Status must be 'occupied' or 'free'")
        return v


class SensorUpdateResponse(BaseModel):
    """Response model for sensor update confirmation."""
    success: bool
    message: str
    spot_id: str
    new_status: ParkingSpotStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ParkingStatusResponse(BaseModel):
    """Response model for parking status overview."""
    total_spots: int
    available: int
    reserved: int
    occupied: int
    spots: List[ParkingSpot]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ReleaseRequest(BaseModel):
    """Request model for manually releasing a parking spot."""
    spot_id: str = Field(..., description="ID of the spot to release")
    reason: Optional[str] = Field(
        default=None,
        description="Optional reason for early release"
    )
