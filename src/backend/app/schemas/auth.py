"""Pydantic schemas for authentication."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    id: UUID
    username: str
    role: str

    model_config = {"from_attributes": True}
