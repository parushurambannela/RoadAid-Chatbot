"""
auth.py

Login / token endpoints.
POST /api/v1/auth/login  → {access_token, token_type, name}
GET  /api/v1/auth/me     → {email, name}  (protected — requires Bearer token)
"""

import logging
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr

from app.services.auth_service import authenticate_user, create_access_token, decode_token

logger = logging.getLogger(__name__)
router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ── Request / Response models ─────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    name: str


class UserInfo(BaseModel):
    email: str
    name: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
async def login(data: LoginRequest):
    """
    Authenticate with email + password.
    Returns a JWT access token valid for 24 hours.
    """
    user = await authenticate_user(data.email, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": user["email"], "name": user.get("name", "")})
    logger.info("Login successful for %s", data.email)
    return TokenResponse(access_token=token, name=user.get("name", ""))


@router.get("/auth/me", response_model=UserInfo, tags=["Auth"])
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Return the logged-in user's info from their JWT token."""
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return UserInfo(email=payload["sub"], name=payload.get("name", ""))
