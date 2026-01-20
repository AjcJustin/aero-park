"""
AeroPark Smart System - Application Principale
Point d'entrée FastAPI avec toutes les configurations.
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging
import sys
from datetime import datetime

# Import routers
from routers import (
    auth_router,
    parking_router,
    admin_router,
    sensor_router,
    websocket_router,
    access_router,
    barrier_router,
    payment_router,
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
    Gestionnaire du cycle de vie de l'application.
    Gère les événements de démarrage et d'arrêt.
    """
    # ===== DÉMARRAGE =====
    logger.info("🚀 Démarrage d'AeroPark Smart System...")
    
    try:
        # Initialiser Firebase
        logger.info("Initialisation de Firebase...")
        init_firebase()
        logger.info("✅ Firebase initialisé")
        
        # Initialiser les places de parking par défaut
        logger.info("Vérification des places de parking...")
        settings = get_settings()
        db = get_db()
        await db.initialize_default_places(count=settings.total_parking_slots)
        logger.info(f"✅ {settings.total_parking_slots} places de parking prêtes")
        
        # Démarrer le scheduler en arrière-plan
        logger.info("Démarrage du scheduler...")
        start_scheduler()
        logger.info("✅ Scheduler démarré")
        
        logger.info("🎉 AeroPark Smart System est prêt!")
        
    except Exception as e:
        logger.error(f"❌ Erreur de démarrage: {e}")
        raise
    
    yield  # L'application s'exécute ici
    
    # ===== ARRÊT =====
    logger.info("🛑 Arrêt d'AeroPark Smart System...")
    
    try:
        stop_scheduler()
        logger.info("✅ Scheduler arrêté")
    except Exception as e:
        logger.error(f"Erreur d'arrêt: {e}")
    
    logger.info("👋 Arrêt d'AeroPark Smart System terminé")


# Créer l'application FastAPI
app = FastAPI(
    title="AeroPark Smart System",
    description="""
    ## Système de Gestion de Parking Aéroportuaire
    
    Une solution de gestion de parking IoT complète:
    
    * **Monitoring en Temps Réel**: Capteurs ESP32 détectant la présence des véhicules
    * **Réservations Intelligentes**: Réserver des places avec gestion automatique du temps
    * **Contrôle de Barrière**: Ouverture/fermeture automatique selon les règles d'accès
    * **Paiement Mobile Money**: Simulation ORANGE_MONEY, AIRTEL_MONEY, MPESA
    * **Mises à Jour WebSocket**: Actualisations en direct pour tous les clients
    * **Intégration Firebase**: Authentification sécurisée et base de données
    
    ### API Capteurs & Barrière
    
    * **POST /api/v1/sensor/update**: Mise à jour de l'état d'une place
    * **POST /api/v1/barrier/open**: Ouvrir la barrière
    * **POST /api/v1/barrier/close**: Fermer la barrière
    * **POST /api/v1/access/validate-code**: Valider un code d'accès
    
    ### Sécurité
    
    * Endpoints capteurs/barrière: Clé API dans le header X-API-Key
    * Endpoints utilisateurs: Token Firebase (Bearer authentication)
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Récupérer les settings
settings = get_settings()

# Configurer CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== GESTIONNAIRES D'EXCEPTIONS ====================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Gère les erreurs de validation Pydantic."""
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
            "detail": "Erreur de validation",
            "errors": errors
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Gère les exceptions inattendues."""
    logger.error(f"Erreur inattendue: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Une erreur inattendue s'est produite",
            "type": type(exc).__name__
        }
    )


# ==================== INCLUSION DES ROUTERS ====================

# Routes API v1 pour les capteurs ESP32 (utilisé par l'ESP32)
app.include_router(sensor_router, prefix="/api/v1/sensor")

# Route WebSocket (sans préfixe - le chemin complet /ws/parking est dans le router)
app.include_router(websocket_router)

# Routes utilisateurs et parking
app.include_router(auth_router)
app.include_router(parking_router)
app.include_router(admin_router)

# Routes nouvelles fonctionnalités: accès, barrières, paiements
app.include_router(access_router)
app.include_router(barrier_router)
app.include_router(payment_router)


# ==================== ENDPOINTS RACINE ====================

@app.get(
    "/",
    tags=["Health"],
    summary="Endpoint Racine",
    description="Retourne les informations de base de l'API."
)
async def root():
    """
    Endpoint racine.
    Retourne les informations de base et le statut de l'API.
    """
    return {
        "name": "AeroPark Smart System",
        "version": "1.0.0",
        "status": "operational",
        "documentation": "/docs",
        "websocket": "/ws/parking",
        "sensor_endpoint": "/api/v1/sensor/update",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get(
    "/health",
    tags=["Health"],
    summary="Vérification de Santé",
    description="Retourne l'état de santé du système."
)
async def health_check():
    """
    Endpoint de vérification de santé.
    Utilisé pour le monitoring et les health checks des load balancers.
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
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get(
    "/api/v1/info",
    tags=["Health"],
    summary="Informations API",
    description="Retourne les informations détaillées de l'API."
)
async def api_info():
    """
    Informations détaillées de l'API.
    Retourne la version, les endpoints et les détails de configuration.
    """
    return {
        "name": "AeroPark Smart System API",
        "version": "1.0.0",
        "endpoints": {
            "sensor_update": "/api/v1/sensor/update",
            "sensor_health": "/api/v1/sensor/health",
            "websocket": "/ws/parking",
            "auth": "/users",
            "parking": "/parking",
            "admin": "/admin/parking"
        },
        "api_key": "Utiliser le header X-API-Key pour les endpoints /sensor",
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }


# ==================== POINT D'ENTRÉE PRINCIPAL ====================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info"
    )
