"""
AeroPark Smart System - REST Authentication Router
Handles user authentication via Firebase REST API (no client SDK needed).
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
import httpx
import logging
import os

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/auth",
    tags=["Authentication REST"],
    responses={
        400: {"description": "Bad request"},
        401: {"description": "Unauthorized"}
    }
)

# Firebase Web API Key - set this in .env
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY", "")

# Firebase REST API endpoints
FIREBASE_SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
FIREBASE_SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
FIREBASE_GET_USER_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_API_KEY}"


class RegisterRequest(BaseModel):
    """Request model for user registration."""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    """Request model for user login."""
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    """Response model for authentication."""
    success: bool
    token: str
    refresh_token: str = ""
    expires_in: int = 3600
    user: dict
    message: str = ""


@router.post(
    "/register",
    response_model=AuthResponse,
    summary="Register New User",
    description="Create a new user account using Firebase REST API."
)
async def register(request: RegisterRequest):
    """
    Register a new user with email and password.
    Uses Firebase REST API - no client SDK needed.
    """
    if not FIREBASE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Firebase API key not configured"
        )
    
    try:
        async with httpx.AsyncClient() as client:
            # Create user with Firebase
            response = await client.post(
                FIREBASE_SIGNUP_URL,
                json={
                    "email": request.email,
                    "password": request.password,
                    "returnSecureToken": True
                },
                timeout=30.0
            )
            
            data = response.json()
            
            if response.status_code != 200:
                error_message = data.get("error", {}).get("message", "Registration failed")
                if "EMAIL_EXISTS" in error_message:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Un compte existe déjà avec cet email"
                    )
                elif "WEAK_PASSWORD" in error_message:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Le mot de passe doit contenir au moins 6 caractères"
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Erreur inscription: {error_message}"
                    )
            
            # Get the ID token and user info
            id_token = data.get("idToken")
            refresh_token = data.get("refreshToken")
            expires_in = int(data.get("expiresIn", 3600))
            user_id = data.get("localId")
            email = data.get("email")
            
            # Update display name using Firebase Admin SDK
            try:
                from firebase_admin import auth
                auth.update_user(user_id, display_name=request.name)
            except Exception as e:
                logger.warning(f"Could not update display name: {e}")
            
            return AuthResponse(
                success=True,
                token=id_token,
                refresh_token=refresh_token,
                expires_in=expires_in,
                user={
                    "uid": user_id,
                    "email": email,
                    "name": request.name,
                    "role": "user"
                },
                message="Inscription réussie"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'inscription"
        )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="User Login",
    description="Authenticate user with email and password using Firebase REST API."
)
async def login(request: LoginRequest):
    """
    Login with email and password.
    Uses Firebase REST API - no client SDK needed.
    """
    if not FIREBASE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Firebase API key not configured"
        )
    
    try:
        async with httpx.AsyncClient() as client:
            # Sign in with Firebase
            response = await client.post(
                FIREBASE_SIGNIN_URL,
                json={
                    "email": request.email,
                    "password": request.password,
                    "returnSecureToken": True
                },
                timeout=30.0
            )
            
            data = response.json()
            
            if response.status_code != 200:
                error_message = data.get("error", {}).get("message", "Login failed")
                if "EMAIL_NOT_FOUND" in error_message or "INVALID_PASSWORD" in error_message or "INVALID_LOGIN_CREDENTIALS" in error_message:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Email ou mot de passe incorrect"
                    )
                elif "USER_DISABLED" in error_message:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Ce compte a été désactivé"
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Erreur connexion: {error_message}"
                    )
            
            id_token = data.get("idToken")
            refresh_token = data.get("refreshToken")
            expires_in = int(data.get("expiresIn", 3600))
            user_id = data.get("localId")
            email = data.get("email")
            display_name = data.get("displayName", "")
            
            # Check if user is admin (you can customize this logic)
            is_admin = email in ["admin@aeropark.com", "admin@aeropark.cd"]
            
            return AuthResponse(
                success=True,
                token=id_token,
                refresh_token=refresh_token,
                expires_in=expires_in,
                user={
                    "uid": user_id,
                    "email": email,
                    "name": display_name or email.split("@")[0],
                    "role": "admin" if is_admin else "user"
                },
                message="Connexion réussie"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la connexion"
        )


@router.post(
    "/refresh",
    summary="Refresh Token",
    description="Get a new ID token using refresh token."
)
async def refresh_token(refresh_token: str):
    """
    Refresh the authentication token.
    """
    if not FIREBASE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Firebase API key not configured"
        )
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}",
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token
                },
                timeout=30.0
            )
            
            data = response.json()
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token"
                )
            
            return {
                "success": True,
                "token": data.get("id_token"),
                "refresh_token": data.get("refresh_token"),
                "expires_in": data.get("expires_in")
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error refreshing token"
        )
