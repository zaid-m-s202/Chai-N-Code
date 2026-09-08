"""FastAPI dependencies for authentication, authorization and database session."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Retrieve user from JWT token. Returns None if unauthenticated."""
    if not credentials:
        return None
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None

    user = db.query(User).filter(User.username == username).first()
    return user


def require_auth(user: Optional[User] = Depends(get_current_user)) -> User:
    """Ensure user is logged in."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_verifying_officer(user: User = Depends(require_auth)) -> User:
    """Ensure user holds VERIFYING_OFFICER or ADMIN role (PRD §5.11 / §9 Acceptance Criterion 8)."""
    if user.role not in ("VERIFYING_OFFICER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an authorized VERIFYING_OFFICER or ADMIN may verify or reject properties",
        )
    return user


def require_legal_access(user: User = Depends(require_auth)) -> User:
    """Ensure user holds VERIFYING_OFFICER or ADMIN role for mutating legal linkages or viewing unmasked owner identities."""
    if user.role not in ("VERIFYING_OFFICER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted: viewing or managing full legal registry and owner identity records requires VERIFYING_OFFICER or ADMIN role",
        )
    return user
