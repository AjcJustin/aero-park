"""
AeroPark Smart System - API Key Authentication Module
Handles API key validation for ESP32 sensors and admin operations.
"""

from fastapi import Depends, HTTPException, status, Header
from typing import Optional
import secrets
import logging

from config import get_settings

# Configure logging
logger = logging.getLogger(__name__)


async def verify_sensor_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_sensor_id: Optional[str] = Header(None, alias="X-Sensor-ID"),
) -> dict:
    """
    Verify API key for ESP32 sensor requests.
    
    ESP32 devices must send:
    - X-API-Key: The sensor API key
    - X-Sensor-ID: Unique identifier for the sensor (optional but recommended)
    
    Args:
        x_api_key: API key from request header
        x_sensor_id: Sensor identifier from request header
        
    Returns:
        dict: Sensor authentication info
        
    Raises:
        HTTPException: If API key is invalid or missing
    """
    if not x_api_key:
        logger.warning("Sensor request without API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include 'X-API-Key' header.",
        )
    
    settings = get_settings()
    
    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(x_api_key, settings.sensor_api_key):
        logger.warning(f"Invalid sensor API key attempted from sensor: {x_sensor_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    
    logger.debug(f"Sensor authenticated: {x_sensor_id or 'unknown'}")
    
    return {
        "authenticated": True,
        "sensor_id": x_sensor_id,
        "type": "sensor"
    }


async def verify_admin_api_key(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
) -> dict:
    """
    Verify admin API key for privileged operations.
    This is an additional layer of security for admin endpoints.
    
    Args:
        x_admin_key: Admin API key from request header
        
    Returns:
        dict: Admin authentication info
        
    Raises:
        HTTPException: If API key is invalid or missing
    """
    if not x_admin_key:
        logger.warning("Admin request without API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing admin API key. Include 'X-Admin-Key' header.",
        )
    
    settings = get_settings()
    
    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(x_admin_key, settings.admin_api_key):
        logger.warning("Invalid admin API key attempted")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin API key",
        )
    
    logger.info("Admin API key verified")
    
    return {
        "authenticated": True,
        "type": "admin"
    }


def generate_api_key(length: int = 32) -> str:
    """
    Generate a secure random API key.
    Utility function for generating new API keys.
    
    Args:
        length: Length of the API key (default 32 characters)
        
    Returns:
        str: Secure random API key
    """
    return secrets.token_urlsafe(length)


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for secure storage.
    Note: For this implementation, we compare plain keys,
    but this function can be used for enhanced security.
    
    Args:
        api_key: Plain text API key
        
    Returns:
        str: Hashed API key
    """
    import hashlib
    return hashlib.sha256(api_key.encode()).hexdigest()
