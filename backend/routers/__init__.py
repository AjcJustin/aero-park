"""
AeroPark Smart System - Routers Package
API route handlers.
"""

from routers.auth import router as auth_router
from routers.parking import router as parking_router
from routers.admin import router as admin_router
from routers.sensor import router as sensor_router
from routers.websocket import router as websocket_router
from routers.access import router as access_router
from routers.barrier import router as barrier_router
from routers.payment import router as payment_router

__all__ = [
    "auth_router",
    "parking_router",
    "admin_router",
    "sensor_router",
    "websocket_router",
    "access_router",
    "barrier_router",
    "payment_router",
]
