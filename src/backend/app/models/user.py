"""User — minimal RBAC for MVP.

Maps to PRD §5.11.  Production will use Keycloak / OIDC; this table
provides the role model and a simple JWT-based auth layer for the pilot.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Boolean, Uuid

from app.database import Base


# PRD §2 roles
USER_ROLES = ("PUBLIC_VIEWER", "FIELD_SURVEYOR", "VERIFYING_OFFICER", "ADMIN")


class User(Base):
    """Platform user with role-based access."""

    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(128), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), nullable=False, default="PUBLIC_VIEWER")

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<User {self.username} [{self.role}]>"
