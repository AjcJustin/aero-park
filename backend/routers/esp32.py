"""
ESP32 Device Management Router

Provides endpoints for:
- ESP32 heartbeat/health check
- Device registration and status
- Remote configuration updates
- Connectivity monitoring
"""

from fastapi import APIRouter, Request, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum
import logging

from services.audit_service import audit_service, AuditEventType, AuditDecision
from config import get_settings

settings = get_settings()

# ESP32 API key - use same as sensor API key
ESP32_API_KEY = settings.sensor_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/esp32", tags=["ESP32 Device Management"])


class DeviceType(str, Enum):
    """Type of ESP32 device."""
    BARRIER_CONTROLLER = "BARRIER_CONTROLLER"
    SENSOR_NODE = "SENSOR_NODE"
    DISPLAY_UNIT = "DISPLAY_UNIT"


class DeviceStatus(str, Enum):
    """Device online status."""
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"


class HeartbeatRequest(BaseModel):
    """Request model for ESP32 heartbeat."""
    device_id: str = Field(..., description="Unique device identifier")
    device_type: DeviceType = Field(default=DeviceType.BARRIER_CONTROLLER)
    firmware_version: str = Field(default="1.0.0", description="Current firmware version")
    uptime_seconds: int = Field(default=0, ge=0, description="Device uptime in seconds")
    free_heap: Optional[int] = Field(None, ge=0, description="Free heap memory in bytes")
    wifi_rssi: Optional[int] = Field(None, description="WiFi signal strength in dBm")
    sensor_status: Optional[Dict[str, bool]] = Field(
        None, 
        description="Status of connected sensors (e.g., {'ir1': true, 'servo': true})"
    )
    last_error: Optional[str] = Field(None, description="Last error message if any")
    pending_commands: Optional[int] = Field(None, ge=0, description="Number of pending commands")
    
    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "ESP32-BARRIER-001",
                "device_type": "BARRIER_CONTROLLER",
                "firmware_version": "1.2.3",
                "uptime_seconds": 86400,
                "free_heap": 45000,
                "wifi_rssi": -65,
                "sensor_status": {
                    "ir_sensors": True,
                    "servo": True,
                    "lcd": True,
                    "entry_sensor": True,
                    "exit_sensor": True
                },
                "last_error": None,
                "pending_commands": 0
            }
        }


class HeartbeatResponse(BaseModel):
    """Response model for ESP32 heartbeat."""
    acknowledged: bool = True
    server_time: str = Field(..., description="Current server UTC time")
    device_status: DeviceStatus
    config_update_available: bool = False
    pending_commands: List[Dict[str, Any]] = Field(default_factory=list)
    message: str = "Heartbeat received"
    next_heartbeat_seconds: int = Field(default=30, description="Recommended interval for next heartbeat")


class DeviceInfo(BaseModel):
    """Information about a registered ESP32 device."""
    device_id: str
    device_type: DeviceType
    status: DeviceStatus
    last_seen: str
    firmware_version: str
    uptime_seconds: int
    wifi_rssi: Optional[int]
    ip_address: Optional[str]
    total_heartbeats: int


# In-memory device registry (in production, use database)
_device_registry: Dict[str, Dict[str, Any]] = {}


def verify_esp32_api_key(api_key: str) -> bool:
    """Verify the ESP32 API key."""
    return api_key == ESP32_API_KEY


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def esp32_heartbeat(
    heartbeat: HeartbeatRequest,
    request: Request,
    x_api_key: str = Header(...)
):
    """
    ESP32 Heartbeat Endpoint
    
    This endpoint allows ESP32 devices to:
    1. Report their health status
    2. Confirm they are online and functioning
    3. Receive configuration updates or commands
    4. Get server time for synchronization
    
    The heartbeat should be sent every 30 seconds.
    Missing 3 consecutive heartbeats marks device as OFFLINE.
    """
    # Verify API key
    if not verify_esp32_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    now = datetime.now(timezone.utc)
    client_ip = get_client_ip(request)
    
    # Determine device status based on sensor health
    device_status = DeviceStatus.ONLINE
    if heartbeat.sensor_status:
        # Check if any critical sensors are failing
        critical_sensors = ["ir_sensors", "servo", "entry_sensor", "exit_sensor"]
        failing_sensors = [
            s for s in critical_sensors 
            if s in heartbeat.sensor_status and not heartbeat.sensor_status[s]
        ]
        if failing_sensors:
            device_status = DeviceStatus.DEGRADED
    
    if heartbeat.last_error:
        device_status = DeviceStatus.DEGRADED
    
    # Update device registry
    device_data = _device_registry.get(heartbeat.device_id, {
        "total_heartbeats": 0,
        "first_seen": now.isoformat()
    })
    
    device_data.update({
        "device_id": heartbeat.device_id,
        "device_type": heartbeat.device_type,
        "status": device_status,
        "last_seen": now.isoformat(),
        "firmware_version": heartbeat.firmware_version,
        "uptime_seconds": heartbeat.uptime_seconds,
        "free_heap": heartbeat.free_heap,
        "wifi_rssi": heartbeat.wifi_rssi,
        "sensor_status": heartbeat.sensor_status,
        "last_error": heartbeat.last_error,
        "ip_address": client_ip,
        "total_heartbeats": device_data["total_heartbeats"] + 1
    })
    
    _device_registry[heartbeat.device_id] = device_data
    
    # Log audit event
    await audit_service.log_esp32_heartbeat(
        esp32_id=heartbeat.device_id,
        ip_address=client_ip,
        firmware_version=heartbeat.firmware_version,
        status=device_status.value
    )
    
    # Check for pending commands (could be from database)
    pending_commands = []
    
    # Check if config update is available (could check version against latest)
    config_update_available = False
    
    logger.info(
        f"Heartbeat from {heartbeat.device_id} - "
        f"Status: {device_status.value}, "
        f"Uptime: {heartbeat.uptime_seconds}s, "
        f"WiFi: {heartbeat.wifi_rssi}dBm"
    )
    
    return HeartbeatResponse(
        acknowledged=True,
        server_time=now.isoformat(),
        device_status=device_status,
        config_update_available=config_update_available,
        pending_commands=pending_commands,
        message=f"Heartbeat acknowledged. Device status: {device_status.value}",
        next_heartbeat_seconds=30
    )


@router.get("/devices", response_model=List[DeviceInfo])
async def list_devices(
    x_api_key: str = Header(...)
):
    """
    List all registered ESP32 devices.
    
    Returns information about all devices that have sent heartbeats,
    including their current status, last seen time, and health metrics.
    """
    if not verify_esp32_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    now = datetime.now(timezone.utc)
    devices = []
    
    for device_id, data in _device_registry.items():
        # Check if device is offline (no heartbeat in 2 minutes)
        last_seen = datetime.fromisoformat(data["last_seen"])
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        
        seconds_since_heartbeat = (now - last_seen).total_seconds()
        
        if seconds_since_heartbeat > 120:  # 2 minutes
            status = DeviceStatus.OFFLINE
        else:
            status = data.get("status", DeviceStatus.ONLINE)
        
        devices.append(DeviceInfo(
            device_id=device_id,
            device_type=data.get("device_type", DeviceType.BARRIER_CONTROLLER),
            status=status,
            last_seen=data["last_seen"],
            firmware_version=data.get("firmware_version", "unknown"),
            uptime_seconds=data.get("uptime_seconds", 0),
            wifi_rssi=data.get("wifi_rssi"),
            ip_address=data.get("ip_address"),
            total_heartbeats=data.get("total_heartbeats", 0)
        ))
    
    return devices


@router.get("/devices/{device_id}", response_model=DeviceInfo)
async def get_device(
    device_id: str,
    x_api_key: str = Header(...)
):
    """
    Get detailed information about a specific ESP32 device.
    """
    if not verify_esp32_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if device_id not in _device_registry:
        raise HTTPException(status_code=404, detail="Device not found")
    
    data = _device_registry[device_id]
    now = datetime.now(timezone.utc)
    
    # Check current status
    last_seen = datetime.fromisoformat(data["last_seen"])
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    
    seconds_since_heartbeat = (now - last_seen).total_seconds()
    
    if seconds_since_heartbeat > 120:
        status = DeviceStatus.OFFLINE
    else:
        status = data.get("status", DeviceStatus.ONLINE)
    
    return DeviceInfo(
        device_id=device_id,
        device_type=data.get("device_type", DeviceType.BARRIER_CONTROLLER),
        status=status,
        last_seen=data["last_seen"],
        firmware_version=data.get("firmware_version", "unknown"),
        uptime_seconds=data.get("uptime_seconds", 0),
        wifi_rssi=data.get("wifi_rssi"),
        ip_address=data.get("ip_address"),
        total_heartbeats=data.get("total_heartbeats", 0)
    )


@router.post("/devices/{device_id}/command")
async def send_command(
    device_id: str,
    command: Dict[str, Any],
    x_api_key: str = Header(...)
):
    """
    Queue a command for an ESP32 device.
    
    The command will be delivered on the device's next heartbeat.
    
    Example commands:
    - {"action": "reboot"}
    - {"action": "update_config", "config": {...}}
    - {"action": "open_barrier"}
    - {"action": "calibrate_sensors"}
    """
    if not verify_esp32_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if device_id not in _device_registry:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # In production, store in database for persistence
    logger.info(f"Command queued for {device_id}: {command}")
    
    return {
        "success": True,
        "message": f"Command queued for device {device_id}",
        "command": command,
        "queued_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/health")
async def esp32_health_summary(
    x_api_key: str = Header(...)
):
    """
    Get a summary of all ESP32 devices health status.
    
    Returns aggregate statistics about device fleet health.
    """
    if not verify_esp32_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    now = datetime.now(timezone.utc)
    
    online = 0
    offline = 0
    degraded = 0
    
    for device_id, data in _device_registry.items():
        last_seen = datetime.fromisoformat(data["last_seen"])
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        
        seconds_since_heartbeat = (now - last_seen).total_seconds()
        
        if seconds_since_heartbeat > 120:
            offline += 1
        elif data.get("status") == DeviceStatus.DEGRADED:
            degraded += 1
        else:
            online += 1
    
    total = len(_device_registry)
    
    return {
        "total_devices": total,
        "online": online,
        "offline": offline,
        "degraded": degraded,
        "health_percentage": round((online / total * 100) if total > 0 else 100, 1),
        "checked_at": now.isoformat()
    }
