"""
AeroPark Smart System - Helper Functions
Utility functions used across the application.
"""

from typing import Optional
import re
import string
from datetime import datetime, timedelta


def generate_spot_number(zone: str = "A", index: int = 1) -> str:
    """
    Generate a standardized spot number.
    
    Args:
        zone: Zone letter or name (e.g., "A", "Terminal 1")
        index: Spot index within the zone
        
    Returns:
        str: Formatted spot number (e.g., "A1", "T1-001")
    """
    # Extract first letter if zone is a name
    zone_prefix = zone[0].upper() if zone else "A"
    
    if len(zone) > 2:
        # For named zones like "Terminal 1", use abbreviation
        zone_prefix = "".join(word[0].upper() for word in zone.split()[:2])
        return f"{zone_prefix}-{index:03d}"
    
    return f"{zone_prefix}{index}"


def format_duration(minutes: int) -> str:
    """
    Format duration in minutes to human-readable string.
    
    Args:
        minutes: Duration in minutes
        
    Returns:
        str: Human-readable duration (e.g., "2 hours 30 minutes")
    """
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if remaining_minutes > 0:
        parts.append(f"{remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}")
    
    return " ".join(parts)


def validate_spot_id(spot_id: str) -> bool:
    """
    Validate a parking spot ID format.
    
    Args:
        spot_id: The spot ID to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not spot_id:
        return False
    
    # Firestore document IDs are typically 20 alphanumeric characters
    # But we also support custom IDs
    if len(spot_id) < 1 or len(spot_id) > 100:
        return False
    
    # Allow alphanumeric, hyphens, and underscores
    pattern = r'^[a-zA-Z0-9_-]+$'
    return bool(re.match(pattern, spot_id))


def validate_sensor_id(sensor_id: str) -> bool:
    """
    Validate a sensor ID format.
    
    Args:
        sensor_id: The sensor ID to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not sensor_id:
        return False
    
    # Expected format: ESP32-SENSOR-XXX or similar
    pattern = r'^[A-Za-z0-9_-]{3,50}$'
    return bool(re.match(pattern, sensor_id))


def calculate_time_remaining(end_time: datetime) -> dict:
    """
    Calculate time remaining until a datetime.
    
    Args:
        end_time: The end datetime
        
    Returns:
        dict: Breakdown of remaining time
    """
    now = datetime.utcnow()
    
    if end_time <= now:
        return {
            "expired": True,
            "total_seconds": 0,
            "hours": 0,
            "minutes": 0,
            "seconds": 0,
            "formatted": "Expired"
        }
    
    delta = end_time - now
    total_seconds = int(delta.total_seconds())
    
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    # Format string
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 and hours == 0:
        parts.append(f"{seconds}s")
    
    return {
        "expired": False,
        "total_seconds": total_seconds,
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds,
        "formatted": " ".join(parts) if parts else "Less than 1 second"
    }


def sanitize_string(value: str, max_length: int = 100) -> str:
    """
    Sanitize a string input for safe storage.
    
    Args:
        value: The string to sanitize
        max_length: Maximum allowed length
        
    Returns:
        str: Sanitized string
    """
    if not value:
        return ""
    
    # Remove control characters
    value = "".join(char for char in value if char.isprintable())
    
    # Trim whitespace
    value = value.strip()
    
    # Truncate if necessary
    if len(value) > max_length:
        value = value[:max_length]
    
    return value


def generate_reservation_code(spot_number: str, user_id: str) -> str:
    """
    Generate a short reservation code for display.
    
    Args:
        spot_number: The parking spot number
        user_id: The user's ID
        
    Returns:
        str: Short reservation code
    """
    import hashlib
    from datetime import datetime
    
    # Create a hash from spot, user, and timestamp
    data = f"{spot_number}{user_id}{datetime.utcnow().isoformat()}"
    hash_value = hashlib.md5(data.encode()).hexdigest()[:6].upper()
    
    return f"{spot_number}-{hash_value}"


def parse_duration_string(duration_str: str) -> Optional[int]:
    """
    Parse a duration string into minutes.
    
    Args:
        duration_str: Duration string (e.g., "2h", "30m", "2h30m", "90 minutes")
        
    Returns:
        Optional[int]: Duration in minutes, or None if invalid
    """
    if not duration_str:
        return None
    
    duration_str = duration_str.lower().strip()
    
    # Try simple number (assume minutes)
    try:
        return int(duration_str)
    except ValueError:
        pass
    
    # Parse patterns like "2h", "30m", "2h30m"
    total_minutes = 0
    
    # Hours
    hours_match = re.search(r'(\d+)\s*h', duration_str)
    if hours_match:
        total_minutes += int(hours_match.group(1)) * 60
    
    # Minutes
    minutes_match = re.search(r'(\d+)\s*m', duration_str)
    if minutes_match:
        total_minutes += int(minutes_match.group(1))
    
    return total_minutes if total_minutes > 0 else None


def is_valid_license_plate(plate: str) -> bool:
    """
    Basic validation for license plate format.
    Note: This is a simple check; real validation varies by region.
    
    Args:
        plate: License plate string
        
    Returns:
        bool: True if format seems valid
    """
    if not plate:
        return False
    
    plate = plate.upper().strip()
    
    # Basic: 2-10 alphanumeric characters
    if len(plate) < 2 or len(plate) > 10:
        return False
    
    # Allow letters, numbers, and hyphens
    pattern = r'^[A-Z0-9-]+$'
    return bool(re.match(pattern, plate))
