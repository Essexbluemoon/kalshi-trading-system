"""
auth.py
Phase 1 authentication: simple API key as Bearer token.
Implemented in Phase 4.

Phase 2 plan (outside capital): role-based auth via Supabase Auth or Auth0.
"""
from __future__ import annotations

import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer()


def require_api_key(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    """
    FastAPI dependency. Validates the Bearer token against API_KEY env var.
    Raises 401 if missing or incorrect.
    """
    expected = os.getenv("API_KEY", "")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_KEY environment variable not configured.",
        )
    if credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
