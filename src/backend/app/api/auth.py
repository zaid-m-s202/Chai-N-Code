"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import create_access_token, get_password_hash, require_auth, verify_password
from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserInfo

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(data={"sub": user.username, "role": user.role})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserInfo)
def get_me(current_user: User = Depends(require_auth)):
    return current_user


@router.post("/quick-token", response_model=TokenResponse)
def quick_token(role: str = "VERIFYING_OFFICER", db: Session = Depends(get_db)):
    """Convenience endpoint for role-switching in government UI demo/testing.

    Returns a signed JWT for the requested role (VERIFYING_OFFICER, FIELD_SURVEYOR, PUBLIC_VIEWER, ADMIN),
    creating a demo user in the database if one does not exist.
    """
    valid_roles = {"VERIFYING_OFFICER", "FIELD_SURVEYOR", "PUBLIC_VIEWER", "ADMIN"}
    normalized_role = role.upper()
    if normalized_role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{role}'. Must be one of: {', '.join(sorted(valid_roles))}",
        )

    username_map = {
        "VERIFYING_OFFICER": "officer_sharma",
        "FIELD_SURVEYOR": "surveyor_verma",
        "PUBLIC_VIEWER": "citizen_patel",
        "ADMIN": "admin_cadastre",
    }
    username = username_map[normalized_role]

    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(
            username=username,
            password_hash=get_password_hash("DemoPass123!"),
            role=normalized_role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token(data={"sub": user.username, "role": user.role})
    return TokenResponse(access_token=token)

