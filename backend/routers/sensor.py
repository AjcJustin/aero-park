"""
AeroPark Smart System - Sensor Router
Handles ESP32 sensor updates and communications.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from typing import Optional
import logging
from datetime import datetime

from models.parking import SensorUpdateRequest, SensorUpdateResponse
from security.api_key import verify_sensor_api_key
from services.parking_service import get_parking_service
from database.firebase_db import get_db

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/sensor",
    tags=["Sensor"],
    responses={
        401: {"description": "Unauthorized - Invalid API key"},
        400: {"description": "Bad Request"}
    }
)


@router.post(
    "/update",
    response_model=SensorUpdateResponse,
    summary="Update Spot Status from Sensor",
    description="Receive parking spot status update from ESP32 sensor."
)
async def sensor_update(
    request: SensorUpdateRequest,
    sensor_auth: dict = Depends(verify_sensor_api_key)
) -> SensorUpdateResponse:
    """
    Receive and process sensor status update.
    
    ESP32 sensors call this endpoint to report parking spot occupancy.
    The endpoint is secured with an API key that must be included
    in the X-API-Key header.
    
    When a sensor reports:
    - 'occupied': If spot was RESERVED → changes to OCCUPIED
                  If spot was AVAILABLE → changes to OCCUPIED (unauthorized parking)
    - 'free': If spot was OCCUPIED → changes to AVAILABLE
    
    Args:
        request: Sensor update with spot_id and status
        sensor_auth: Verified sensor authentication
        
    Returns:
        SensorUpdateResponse: Confirmation of status update
    """
    try:
        service = get_parking_service()
        
        # Determine if occupied based on sensor reading
        is_occupied = request.status.lower() == "occupied"
        
        # Use sensor_id from request or from auth header
        sensor_id = request.sensor_id or sensor_auth.get("sensor_id")
        
        result = await service.update_from_sensor(
            spot_id=request.spot_id,
            is_occupied=is_occupied,
            sensor_id=sensor_id
        )
        
        logger.info(
            f"Sensor update: spot={request.spot_id}, "
            f"status={request.status}, sensor={sensor_id}"
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Sensor update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing sensor update"
        )


@router.post(
    "/heartbeat",
    summary="Sensor Heartbeat",
    description="Register sensor heartbeat for monitoring."
)
async def sensor_heartbeat(
    sensor_id: str,
    sensor_auth: dict = Depends(verify_sensor_api_key)
):
    """
    Register sensor heartbeat.
    
    ESP32 sensors can call this endpoint periodically to indicate
    they are online and functioning. Useful for monitoring sensor health.
    
    Args:
        sensor_id: The sensor's identifier
        
    Returns:
        Acknowledgment of heartbeat
    """
    try:
        db = get_db()
        
        # Log heartbeat (could be stored in a separate collection for monitoring)
        logger.debug(f"Heartbeat received from sensor: {sensor_id}")
        
        return {
            "success": True,
            "message": "Heartbeat registered",
            "sensor_id": sensor_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Heartbeat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing heartbeat"
        )


@router.get(
    "/config/{sensor_id}",
    summary="Get Sensor Configuration",
    description="Get configuration for a specific sensor."
)
async def get_sensor_config(
    sensor_id: str,
    sensor_auth: dict = Depends(verify_sensor_api_key)
):
    """
    Get sensor configuration.
    
    Returns configuration parameters for the sensor,
    including the spot it monitors and update interval.
    
    Args:
        sensor_id: The sensor's identifier
        
    Returns:
        Sensor configuration
    """
    try:
        db = get_db()
        
        # Find spot associated with this sensor
        spot = await db.get_spot_by_sensor_id(sensor_id)
        
        if not spot:
            return {
                "configured": False,
                "sensor_id": sensor_id,
                "message": "Sensor not assigned to any spot"
            }
        
        return {
            "configured": True,
            "sensor_id": sensor_id,
            "spot_id": spot.get("id"),
            "spot_number": spot.get("spot_number"),
            "update_interval_ms": 5000,  # 5 seconds
            "distance_threshold_cm": 50,  # Object closer than 50cm = occupied
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Config fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching configuration"
        )


@router.post(
    "/batch-update",
    summary="Batch Sensor Update",
    description="Process multiple sensor updates in one request."
)
async def batch_sensor_update(
    updates: list[SensorUpdateRequest],
    sensor_auth: dict = Depends(verify_sensor_api_key)
):
    """
    Process batch sensor updates.
    
    Allows a central controller or gateway to report multiple
    sensor readings in a single request.
    
    Args:
        updates: List of sensor updates
        
    Returns:
        Results of all updates
    """
    try:
        service = get_parking_service()
        results = []
        
        for update in updates:
            try:
                is_occupied = update.status.lower() == "occupied"
                result = await service.update_from_sensor(
                    spot_id=update.spot_id,
                    is_occupied=is_occupied,
                    sensor_id=update.sensor_id
                )
                results.append({
                    "spot_id": update.spot_id,
                    "success": True,
                    "new_status": result.new_status.value
                })
            except Exception as e:
                results.append({
                    "spot_id": update.spot_id,
                    "success": False,
                    "error": str(e)
                })
        
        logger.info(f"Batch update processed: {len(updates)} sensors")
        
        return {
            "processed": len(updates),
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Batch update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing batch update"
        )
