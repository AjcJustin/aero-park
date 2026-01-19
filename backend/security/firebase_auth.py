"""
AeroPark Smart System - Firebase Authentication Module
Handles Firebase ID token verification and user extraction.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth
from typing import Optional
import logging

from models.user import UserProfile, UserRole, TokenPayload
from database.firebase_db import get_db

# Configure logging
logger = logging.getLogger(__name__)

# Security scheme for Bearer token
bearer_scheme = HTTPBearer(auto_error=False)


async def verify_firebase_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> TokenPayload:
    """
    Verify Firebase ID token from Authorization header.
    Returns decoded token payload.
    
    Args:
        credentials: Bearer token from Authorization header
        
    Returns:
        TokenPayload: Decoded token information
        
    Raises:
        HTTPException: If token is invalid or missing
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    try:
        # Verify the Firebase ID token
        decoded_token = auth.verify_id_token(token)
        
        return TokenPayload(
            uid=decoded_token.get("uid"),
            email=decoded_token.get("email"),
            email_verified=decoded_token.get("email_verified", False),
            name=decoded_token.get("name"),
            picture=decoded_token.get("picture"),
            auth_time=decoded_token.get("auth_time"),
            iat=decoded_token.get("iat"),
            exp=decoded_token.get("exp"),
            firebase=decoded_token.get("firebase"),
        )
        
    except auth.ExpiredIdTokenError:
        logger.warning("Expired Firebase token received")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    except auth.RevokedIdTokenError:
        logger.warning("Revoked Firebase token received")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    except auth.InvalidIdTokenError as e:
        logger.warning(f"Invalid Firebase token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error",
        )


async def get_current_user(
    token: TokenPayload = Depends(verify_firebase_token)
) -> UserProfile:
    """
    Get the current authenticated user profile.
    Creates/updates user profile in Firestore.
    
    Args:
        token: Verified Firebase token payload
        
    Returns:
        UserProfile: Current user's profile
    """
    try:
        db = get_db()
        
        # Get or create user profile
        user_data = await db.get_user_profile(token.uid)
        
        # Determine user role (check custom claims or Firestore)
        role = UserRole.USER
        if user_data and user_data.get("role") == "admin":
            role = UserRole.ADMIN
        
        # Create profile object
        profile = UserProfile(
            uid=token.uid,
            email=token.email,
            display_name=token.name,
            photo_url=token.picture,
            email_verified=token.email_verified,
            role=role,
        )
        
        # Update last login in Firestore
        await db.upsert_user_profile(token.uid, {
            "uid": token.uid,
            "email": token.email,
            "display_name": token.name,
            "photo_url": token.picture,
            "email_verified": token.email_verified,
            "role": role.value,
        })
        
        return profile
        
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user profile",
        )


async def get_current_admin(
    user: UserProfile = Depends(get_current_user)
) -> UserProfile:
    """
    Verify that the current user has admin privileges.
    
    Args:
        user: Current authenticated user
        
    Returns:
        UserProfile: Admin user's profile
        
    Raises:
        HTTPException: If user is not an admin
    """
    if user.role != UserRole.ADMIN:
        logger.warning(f"Non-admin user {user.uid} attempted admin action")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> Optional[UserProfile]:
    """
    Optionally get the current user if authenticated.
    Returns None if no valid token is provided.
    
    Args:
        credentials: Optional Bearer token
        
    Returns:
        Optional[UserProfile]: User profile or None
    """
    if credentials is None:
        return None
    
    try:
        token = await verify_firebase_token(credentials)
        return await get_current_user(token)
    except HTTPException:
        return None
