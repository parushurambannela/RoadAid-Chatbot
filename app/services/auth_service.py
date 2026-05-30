"""
auth_service.py

Handles password verification and JWT creation / decoding.

Users are stored in the MongoDB `users` collection with fields:
    email    : str  (unique)
    name     : str
    password : str  (bcrypt hash)

To create a test user run:
    python create_test_user.py
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.database.mongo_client import get_db

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

SECRET_KEY  = os.getenv("JWT_SECRET_KEY", "change-this-secret-in-production")
ALGORITHM   = "HS256"
EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Helpers ───────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    """Create a JWT token that expires in EXPIRE_HOURS hours."""
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(hours=EXPIRE_HOURS)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT. Returns the payload dict or None."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        logger.debug("JWT decode failed: %s", exc)
        return None


# ── Main auth function ────────────────────────────────────────────────────────

async def authenticate_user(email: str, password: str) -> Optional[dict]:
    """
    Look up the user in MongoDB and verify their password.
    Returns the user document (minus password) on success, None on failure.
    """
    db = get_db()
    if db is None:
        logger.error("MongoDB not connected — cannot authenticate.")
        return None

    user = await db["users"].find_one({"email": email.lower()})
    if not user:
        logger.debug("Login attempt for unknown email: %s", email)
        return None

    if not verify_password(password, user.get("password", "")):
        logger.debug("Wrong password for %s", email)
        return None

    return {"email": user["email"], "name": user.get("name", "")}
