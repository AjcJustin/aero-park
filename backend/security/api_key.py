"""
AeroPark Smart System - API Key Authentication Module
Validation de la clé API pour les capteurs ESP32.
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
) -> dict:
    """
    Vérifie la clé API des capteurs ESP32.
    
    L'ESP32 doit envoyer:
    - X-API-Key: La clé API du capteur (aeropark-sensor-key-2024)
    
    Args:
        x_api_key: Clé API depuis l'en-tête
        
    Returns:
        dict: Info d'authentification du capteur
        
    Raises:
        HTTPException: Si la clé API est invalide ou manquante
    """
    if not x_api_key:
        logger.warning("Requête capteur sans clé API")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API manquante. Ajoutez l'en-tête 'X-API-Key'.",
        )
    
    settings = get_settings()
    
    # Comparaison sécurisée pour éviter les attaques timing
    if not secrets.compare_digest(x_api_key, settings.sensor_api_key):
        logger.warning(f"Clé API capteur invalide: {x_api_key[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide",
        )
    
    logger.debug("Capteur authentifié avec succès")
    
    return {
        "authenticated": True,
        "type": "sensor"
    }


def generate_api_key(length: int = 32) -> str:
    """
    Génère une clé API aléatoire sécurisée.
    
    Args:
        length: Longueur de la clé
        
    Returns:
        str: Clé API aléatoire
    """
    return secrets.token_urlsafe(length)
