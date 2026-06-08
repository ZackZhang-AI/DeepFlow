"""Authentication and ownership helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.core import db

LOCAL_DEFAULT_USER_ID = "local_default_user"
TOKEN_TTL_DAYS = 30

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return f"pbkdf2_sha256$260000${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_bearer_token(user_id: str) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS)).isoformat()
    db.create_auth_session(
        token_hash=token_hash,
        user_id=user_id,
        expires_at=expires_at,
    )
    return token, expires_at


def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
) -> Optional[dict]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None

    return get_user_from_token(credentials.credentials)


def get_user_from_token(token: str) -> Optional[dict]:
    session = db.get_auth_session(_hash_token(token))
    if session is None or _is_expired(session["expires_at"]):
        return None
    return db.get_user_by_id(session["user_id"])


def require_login(user: Annotated[Optional[dict], Depends(get_current_user)]) -> dict:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_resource_owner(resource: Optional[dict], user: dict, owner_field: str = "user_id") -> dict:
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    if resource.get(owner_field) != user["user_id"]:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _is_expired(expires_at: str) -> bool:
    try:
        expires = datetime.fromisoformat(expires_at)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return expires <= datetime.now(timezone.utc)
