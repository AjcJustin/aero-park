"""
AeroPark Smart System - Configuration Module
Gère toutes les variables d'environnement et paramètres.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List
from functools import lru_cache
import os
from pathlib import Path

# Charger le fichier .env manuellement
from dotenv import load_dotenv

# Trouver le fichier .env
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)


class Settings(BaseSettings):
    """Paramètres de l'application chargés depuis les variables d'environnement."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Firebase Configuration
    firebase_project_id: str = Field(default="", alias="FIREBASE_PROJECT_ID")
    firebase_private_key_id: str = Field(default="", alias="FIREBASE_PRIVATE_KEY_ID")
    firebase_private_key: str = Field(default="", alias="FIREBASE_PRIVATE_KEY")
    firebase_client_email: str = Field(default="", alias="FIREBASE_CLIENT_EMAIL")
    firebase_client_id: str = Field(default="", alias="FIREBASE_CLIENT_ID")
    firebase_auth_uri: str = Field(
        default="https://accounts.google.com/o/oauth2/auth",
        alias="FIREBASE_AUTH_URI"
    )
    firebase_token_uri: str = Field(
        default="https://oauth2.googleapis.com/token",
        alias="FIREBASE_TOKEN_URI"
    )
    firebase_auth_provider_cert_url: str = Field(
        default="https://www.googleapis.com/oauth2/v1/certs",
        alias="FIREBASE_AUTH_PROVIDER_CERT_URL"
    )
    firebase_client_cert_url: str = Field(default="", alias="FIREBASE_CLIENT_CERT_URL")
    
    # API Security - Clé API pour les capteurs ESP32
    sensor_api_key: str = Field(
        default="aeropark-sensor-key-2024",
        alias="SENSOR_API_KEY"
    )
    
    # Application Settings
    debug: bool = Field(default=True, alias="DEBUG")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")
    default_reservation_duration_minutes: int = Field(
        default=60,
        alias="DEFAULT_RESERVATION_DURATION_MINUTES"
    )
    max_reservation_duration_minutes: int = Field(
        default=480,
        alias="MAX_RESERVATION_DURATION_MINUTES"
    )
    total_parking_slots: int = Field(default=6, alias="TOTAL_PARKING_SLOTS")
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    def get_firebase_credentials(self) -> dict:
        """Generate Firebase credentials dictionary."""
        import re
        def clean(s: str) -> str:
            if not s: return ""
            # Supprimer tout ce qui n'est pas alphanumérique, ponctuation de base ou markers
            s = s.strip()
            # Supprimer les guillemets englobants
            s = re.sub(r'^["\']|["\']$', '', s)
            return s.strip()

        # Pour la clé privée, c'est spécial
        pk = self.firebase_private_key or ""
        pk = pk.strip()
        pk = re.sub(r'^["\']|["\']$', '', pk)
        pk = pk.replace("\\n", "\n").strip()
        
        # Isolation stricte entre les balises
        if "-----BEGIN PRIVATE KEY-----" in pk:
            parts = pk.split("-----BEGIN PRIVATE KEY-----")
            pk = "-----BEGIN PRIVATE KEY-----" + parts[1]
        if "-----END PRIVATE KEY-----" in pk:
            parts = pk.split("-----END PRIVATE KEY-----")
            pk = parts[0] + "-----END PRIVATE KEY-----"

        creds = {
            "type": "service_account",
            "project_id": clean(self.firebase_project_id),
            "private_key_id": clean(self.firebase_private_key_id),
            "private_key": pk,
            "client_email": clean(self.firebase_client_email),
            "client_id": clean(self.firebase_client_id),
            "auth_uri": clean(self.firebase_auth_uri),
            "token_uri": clean(self.firebase_token_uri),
            "auth_provider_x509_cert_url": clean(self.firebase_auth_provider_cert_url),
            "client_x509_cert_url": clean(self.firebase_client_cert_url),
        }

        import logging
        logger = logging.getLogger("config")
        logger.info(f"Credentials strictly cleaned for project: {creds['project_id']}")
        return creds


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()
