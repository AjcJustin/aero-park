"""
AeroPark Smart System - Main Application
FastAPI application entry point with all configurations.
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging
import sys

# Import routers
from routers import (
    auth_router,
    parking_router,
    admin_router,
    sensor_router,
    websocket_router,
)

# Import utilities
from database.firebase_db import init_firebase, get_db
from utils.scheduler import start_scheduler, stop_scheduler
from config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # ===== STARTUP =====
    logger.info("🚀 Starting AeroPark Smart System...")
    
    try:
        # Initialize Firebase
        logger.info("Initializing Firebase...")
        init_firebase()
        logger.info("✅ Firebase initialized")
        
        # Initialize default parking spots
        logger.info("Checking parking spots...")
        db = get_db()
        await db.initialize_default_spots(count=5)
        logger.info("✅ Parking spots ready")
        
        # Start background scheduler
        logger.info("Starting background scheduler...")
        start_scheduler()
        logger.info("✅ Scheduler started")
        
        logger.info("🎉 AeroPark Smart System is ready!")
        
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")
        raise
    
    yield  # Application runs here
    
    # ===== SHUTDOWN =====
    logger.info("🛑 Shutting down AeroPark Smart System...")
    
    try:
        # Stop scheduler
        stop_scheduler()
        logger.info("✅ Scheduler stopped")
        
    except Exception as e:
        logger.error(f"Shutdown error: {e}")
    
    logger.info("👋 AeroPark Smart System shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="AeroPark Smart System",
    description="""
    ## Airport Parking Management System
    
    A comprehensive IoT-enabled parking management solution featuring:
    
    * **Real-time Monitoring**: ESP32 sensors detect vehicle presence
    * **Smart Reservations**: Reserve spots with automatic timing
    * **WebSocket Updates**: Live status updates for all clients
    * **Firebase Integration**: Secure authentication and database
    
    ### API Sections
    
    * **Authentication**: User profile and authentication endpoints
    * **Parking**: View status and manage reservations
    * **Admin**: Manage parking spots and system configuration
    * **Sensor**: ESP32 device communication endpoints
    * **WebSocket**: Real-time updates at `/ws/parking`
    
    ### Security
    
    * User endpoints require Firebase ID token (Bearer authentication)
    * Sensor endpoints require API key (X-API-Key header)
    * Admin endpoints require both admin role and authentication
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Get settings
settings = get_settings()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== EXCEPTION HANDLERS ====================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": errors
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred",
            "type": type(exc).__name__
        }
    )


# ==================== INCLUDE ROUTERS ====================

app.include_router(auth_router)
app.include_router(parking_router)
app.include_router(admin_router)
app.include_router(sensor_router)
app.include_router(websocket_router)


# ==================== ROOT ENDPOINTS ====================

@app.get(
    "/",
    tags=["Health"],
    summary="Root Endpoint",
    description="Returns basic API information."
)
async def root():
    """
    Root endpoint.
    Returns basic API information and status.
    """
    return {
        "name": "AeroPark Smart System",
        "version": "1.0.0",
        "status": "operational",
        "documentation": "/docs",
        "websocket": "/ws/parking"
    }


@app.get(
    "/health",
    tags=["Health"],
    summary="Health Check",
    description="Returns system health status."
)
async def health_check():
    """
    Health check endpoint.
    Used for monitoring and load balancer health checks.
    """
    from services.websocket_service import get_websocket_manager
    from utils.scheduler import get_scheduler
    
    manager = get_websocket_manager()
    scheduler = get_scheduler()
    
    return {
        "status": "healthy",
        "services": {
            "firebase": "connected",
            "scheduler": "running" if scheduler.is_running() else "stopped",
            "websocket_connections": manager.get_connection_count()
        }
    }


@app.get(
    "/api/v1/info",
    tags=["Health"],
    summary="API Information",
    description="Returns detailed API information."
)
async def api_info():
    """
    Detailed API information.
    Returns version, endpoints, and configuration details.
    """
    return {
        "name": "AeroPark Smart System API",
        "version": "1.0.0",
        "endpoints": {
            "auth": "/users",
            "parking": "/parking",
            "admin": "/admin/parking",
            "sensor": "/sensor",
            "websocket": "/ws/parking"
        },
        "features": [
            "Firebase Authentication",
            "Real-time WebSocket updates",
            "ESP32 sensor integration",
            "Automatic reservation expiry",
            "Concurrent reservation handling"
        ],
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        }
    }


# ==================== MAIN ENTRY ====================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info"
    )
