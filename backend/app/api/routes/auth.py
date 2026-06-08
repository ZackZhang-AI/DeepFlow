"""Authentication API routes."""

import sqlite3
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.auth import create_bearer_token, hash_password, require_login, verify_password
from backend.app.core.db import create_user, get_user_by_username
from backend.app.models.schemas import AuthResponse, LoginRequest, RegisterRequest, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(req: RegisterRequest):
    username = req.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if get_user_by_username(username):
        raise HTTPException(status_code=409, detail="Username already exists")

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    try:
        user = create_user(
            user_id=user_id,
            username=username,
            password_hash=hash_password(req.password),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Username already exists") from exc

    token, expires_at = create_bearer_token(user["user_id"])
    return _auth_response(user, token, expires_at)


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    user = get_user_by_username(req.username.strip())
    if not user or not verify_password(req.password, user.get("password_hash") or ""):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token, expires_at = create_bearer_token(user["user_id"])
    return _auth_response(user, token, expires_at)


@router.get("/me", response_model=UserResponse)
async def me(user: dict = Depends(require_login)):
    return _user_response(user)


def _auth_response(user: dict, token: str, expires_at: str) -> AuthResponse:
    return AuthResponse(
        access_token=token,
        expires_at=expires_at,
        user=_user_response(user),
    )


def _user_response(user: dict) -> UserResponse:
    return UserResponse(
        user_id=user["user_id"],
        username=user["username"],
        created_at=user["created_at"],
    )
