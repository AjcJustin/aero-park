"""
AeroPark System - REST Authentication Router
Handles user authentication via Firebase REST API (pas besoin de SDk pour le client)
"""

from fastapi import APIRouter, HTTPException, status, Header
from pydantic import BaseModel, EmailStr, Field
import httpx
import logging
import os
from datetime import datetime
from database.firebase_db import get_db

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
                from firebase_admin import auth as fb_auth
                fb_auth.update_user(user_id, display_name=request.name)
                
                # Also save to Firestore immediately
                from database.firebase_db import get_db
                db = get_db()
                await db.upsert_user_profile(user_id, {
                    "uid": user_id,
                    "email": email,
                    "display_name": request.name,
                    "role": "user"
                })
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
            
            # Check if user is admin (custom claims or email list)
            is_admin = False
            admin_emails = ["admin@aeropark.com", "admin@aeropark.cd", "abrahamfaith325@gmail.com"]
            
            # Fetch Firestore data to get the custom display name
            from database.firebase_db import get_db
            db = get_db()
            user_profile = await db.get_user_profile(user_id)
            if user_profile and user_profile.get("display_name"):
                display_name = user_profile["display_name"]
            
            # Check email list first
            if email in admin_emails:
                is_admin = True
            else:
                # Check custom claims from Firebase
                try:
                    from firebase_admin import auth as fb_auth
                    user_record = fb_auth.get_user(user_id)
                    if user_record.custom_claims and user_record.custom_claims.get("role") == "admin":
                        is_admin = True
                except Exception as e:
                    logger.warning(f"Could not check custom claims: {e}")
            
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


class UpdatePasswordRequest(BaseModel):
    """Request model for password update."""
    current_password: str
    new_password: str = Field(..., min_length=6)


@router.post(
    "/update-password",
    summary="Update Password",
    description="Update the current user's password with re-authentication."
)
async def update_password(
    request: UpdatePasswordRequest,
    authorization: str = Header(None)
):
    """
   Update user password with authentication.
    Verifies current password and updates to new password.
    """
    if not FIREBASE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Firebase API key not configured"
        )
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification requis"
        )
    
    id_token = authorization.replace("Bearer ", "")
    
    try:
        # Verify the token to get user info
        from firebase_admin import auth as fb_auth
        decoded_token = fb_auth.verify_id_token(id_token)
        user_id = decoded_token['uid']
        user_email = decoded_token.get('email')
        
        if not user_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email non trouvé"
            )
        
        # Re-authenticate with current password to verify
        async with httpx.AsyncClient() as client:
            auth_response = await client.post(
                FIREBASE_SIGNIN_URL,
                json={
                    "email": user_email,
                    "password": request.current_password,
                    "returnSecureToken": True
                },
                timeout=30.0
            )
            
            if auth_response.status_code != 200:
                auth_data = auth_response.json()
                error_message = auth_data.get("error", {}).get("message", "")
                if "INVALID_PASSWORD" in error_message or "INVALID_LOGIN_CREDENTIALS" in error_message:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Mot de passe actuel incorrect"
                    )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Vérification du mot de passe actuel échouée"
                )
            
            # Current password verified, now update to new password
            # Use Firebase Admin SDK to update password
            fb_auth.update_user(
                user_id,
                password=request.new_password
            )
            
            logger.info(f"Password updated for user {user_id}")
            
            return {
                "success": True,
                "message": "Mot de passe modifié avec succès"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la modification du mot de passe"
        )


class UpdateProfileRequest(BaseModel):
    """Request model for profile update."""
    display_name: str = Field(..., min_length=2, max_length=50)


@router.post(
    "/update-profile-authenticated",
    summary="Update Profile (Authenticated)",
    description="Update the current user's profile information (display name). Requires Bearer token."
)
async def update_profile_authenticated(
    request: UpdateProfileRequest,
    authorization: str = Header(None)
):
    """
    Update user profile with authentication.
    updates display name in Firebase Auth and Firestore.
    """
    if not FIREBASE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Firebase API key not configured"
        )
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification requis"
        )
    
    id_token = authorization.replace("Bearer ", "")
    
    try:
        # Verify the token to get user info
        from firebase_admin import auth as fb_auth
        decoded_token = fb_auth.verify_id_token(id_token)
        user_id = decoded_token['uid']
        
        # Update display name in Firebase Auth
        fb_auth.update_user(
            user_id,
            display_name=request.display_name
        )
        
        # Update display name in Firestore
        db = get_db()
        await db.upsert_user_profile(user_id, {
            "uid": user_id,
            "display_name": request.display_name
        })
        
        logger.info(f"Profile updated for user {user_id}")
        
        return {
            "success": True,
            "message": "Profil mis à jour avec succès",
            "user": {
                "uid": user_id,
                "name": request.display_name
            }
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la mise à jour du profil"
        )


class CreateAdminRequest(BaseModel):
    """Request model for creating a new admin."""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)


@router.post(
    "/create-admin",
    summary="Create Admin User",
    description="Create a new administrator account. Requires existing admin privileges."
)
async def create_admin(
    request: CreateAdminRequest,
    authorization: str = Header(None)
):
    """
    Create a new admin user.
    Requires authentication from an existing admin.
    """
    if not FIREBASE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Firebase API key not configured"
        )
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification requis"
        )
    
    id_token = authorization.replace("Bearer ", "")
    
    try:
        # 1. Verify the requester is an admin
        from firebase_admin import auth as fb_auth
        decoded_token = fb_auth.verify_id_token(id_token)
        requester_uid = decoded_token['uid']
        requester_email = decoded_token.get('email')
        
        # Check if requester has admin role
        is_admin = False
        if decoded_token.get('role') == 'admin':
            is_admin = True
        
        # Fallback to hardcoded admin emails if claims not set
        admin_emails = ["admin@aeropark.com", "admin@aeropark.cd", "abrahamfaith325@gmail.com"]
        if requester_email in admin_emails:
            is_admin = True
            
        if not is_admin:
             # Double check Firestore profile as fallback
            db = get_db()
            requester_profile = await db.get_user_profile(requester_uid)
            if requester_profile and requester_profile.get("role") == "admin":
                is_admin = True
        
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé: privilèges administrateur requis"
            )
            
        # 2. Create the new user in Firebase Auth
        try:
            user_record = fb_auth.create_user(
                email=request.email,
                password=request.password,
                display_name=request.name,
                email_verified=True # Assume verified since created by admin
            )
        except Exception as e:
            error_msg = str(e)
            if "EMAIL_EXISTS" in error_msg:
                raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
            raise HTTPException(status_code=400, detail=f"Erreur création utilisateur: {error_msg}")
            
        # 3. Set custom claims for admin role
        fb_auth.set_custom_user_claims(user_record.uid, {'role': 'admin'})
        
        # 4. Add to Firestore users collection
        db = get_db()
        await db.upsert_user_profile(user_record.uid, {
            "uid": user_record.uid,
            "email": request.email,
            "display_name": request.name,
            "role": "admin",
            "created_at": datetime.utcnow().isoformat(),
            "created_by": requester_email
        })
        
        logger.info(f"New admin created: {request.email} by {requester_email}")
        
        return {
            "success": True,
            "message": " Nouvel administrateur créé avec succès",
            "user": {
                "uid": user_record.uid,
                "email": user_record.email,
                "name": user_record.display_name,
                "role": "admin"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create admin error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne lors de la création de l'administrateur"
        )
