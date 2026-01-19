"""
AeroPark Smart System - Configuration Module
Gère toutes les variables d'environnement et paramètres.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """Paramètres de l'application chargés depuis les variables d'environnement."""
    
    # Firebase Configuration
    firebase_project_id: str = Field(..., env="FIREBASE_PROJECT_ID")
    firebase_private_key_id: str = Field(..., env="FIREBASE_PRIVATE_KEY_ID")
    firebase_private_key: str = Field(..., env="FIREBASE_PRIVATE_KEY")
    firebase_client_email: str = Field(..., env="FIREBASE_CLIENT_EMAIL")
    firebase_client_id: str = Field(..., env="FIREBASE_CLIENT_ID")
    firebase_auth_uri: str = Field(
        default="https://accounts.google.com/o/oauth2/auth",
        env="FIREBASE_AUTH_URI"
    )
    firebase_token_uri: str = Field(
        default="https://oauth2.googleapis.com/token",
        env="FIREBASE_TOKEN_URI"
    )
    firebase_auth_provider_cert_url: str = Field(
        default="https://www.googleapis.com/oauth2/v1/certs",
        env="FIREBASE_AUTH_PROVIDER_CERT_URL"
    )
    firebase_client_cert_url: str = Field(..., env="FIREBASE_CLIENT_CERT_URL")
    
    # API Security - Clé API pour les capteurs ESP32
    sensor_api_key: str = Field(
        default="aeropark-sensor-key-2024",
        env="SENSOR_API_KEY"
    )
    
    # Application Settings
    debug: bool = Field(default=True, env="DEBUG")
    cors_origins: str = Field(default="*", env="CORS_ORIGINS")
    default_reservation_duration_minutes: int = Field(
        default=60,
        env="DEFAULT_RESERVATION_DURATION_MINUTES"
    )
    max_reservation_duration_minutes: int = Field(
        default=480,
        env="MAX_RESERVATION_DURATION_MINUTES"
    )
    total_parking_slots: int = Field(default=6, env="TOTAL_PARKING_SLOTS")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    def get_firebase_credentials(self) -> dict:
        """Generate Firebase credentials dictionary."""
        return {
            "type": "service_account",
            "project_id": self.firebase_project_id,
            "private_key_id": self.firebase_private_key_id,
            "private_key": self.firebase_private_key.replace("\\n", "\n"),
            "client_email": self.firebase_client_email,
            "client_id": self.firebase_client_id,
            "auth_uri": self.firebase_auth_uri,
            "token_uri": self.firebase_token_uri,
            "auth_provider_x509_cert_url": self.firebase_auth_provider_cert_url,
            "client_x509_cert_url": self.firebase_client_cert_url,
        }


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()
