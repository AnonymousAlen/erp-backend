"""
app/routes/auth.py
------------------
Authentication endpoints:
  POST /auth/register  — Pydantic validation, hash password, create User
  POST /auth/login     — Query user, verify password, issue JWT
  POST /auth/oauth     — Query by email; create user if not exists, issue JWT
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.middleware.auth import create_access_token
from app.models.users import User
from app.schemas.auth import LoginRequest, OAuthRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _make_token(user: User) -> TokenResponse:
    token = create_access_token({
        "sub": user.email,
        "role": user.role if isinstance(user.role, str) else user.role.value,
        "user_id": str(user.id),
    })
    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email,
        role=user.role if isinstance(user.role, str) else user.role.value,
    )


# ── Step 1: Register ──────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user.
    - Validates input via Pydantic
    - Hashes password with bcrypt
    - Creates User record, commits, refreshes
    - Returns JWT
    """
    # Check duplicate email
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        password_hash=_hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _make_token(user)


# ── Step 2: Login ─────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with email + password.
    - Queries user by email
    - Verifies bcrypt password
    - Returns JWT on success
    """
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not _verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    return _make_token(user)


# ── Step 3: OAuth ─────────────────────────────────────────────────────────────

@router.post("/oauth", response_model=TokenResponse)
def oauth_login(payload: OAuthRequest, db: Session = Depends(get_db)):
    """
    OAuth login (e.g. Jibble).
    - Queries user by email
    - If not found: creates user with a random unusable password hash
    - Commits and returns JWT
    """
    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        # Create user with OAuth — no usable password
        user = User(
            id=uuid.uuid4(),
            email=payload.email,
            password_hash=_hash_password(str(uuid.uuid4())),  # random, not usable
            full_name=payload.full_name or "OAuth User",
            role="employee",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return _make_token(user)
