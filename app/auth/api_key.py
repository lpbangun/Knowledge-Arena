import secrets
from uuid import UUID

import bcrypt
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.agent import Agent

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def generate_api_key() -> str:
    return f"ka-{secrets.token_urlsafe(32)}"


def hash_api_key(key: str) -> str:
    return bcrypt.hashpw(key.encode(), bcrypt.gensalt()).decode()


def get_key_prefix(key: str) -> str:
    return key[:7]


async def get_current_agent(
    api_key: str = Security(api_key_header),
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    """Authenticate agent via JWT Bearer token (first) or X-API-Key (fallback).

    Try JWT Bearer token first if provided. Falls back to X-API-Key bcrypt validation.
    This allows agents to use either their raw API key or a JWT token from /api/v1/agents/token.
    """
    # Collect the raw token from whichever header was sent
    # Agents may send API key via: X-API-Key header, Bearer token, or even both
    raw_key = api_key  # from X-API-Key header

    if credentials:
        bearer_token = credentials.credentials
        # If bearer token looks like an API key (ka-...), treat it as one
        if bearer_token.startswith("ka-"):
            if not raw_key:
                raw_key = bearer_token
        else:
            # Try JWT decode
            try:
                payload = jwt.decode(bearer_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
                agent_id = UUID(payload["sub"])
                result = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.is_active == True))
                agent = result.scalar_one_or_none()
                if agent:
                    return agent
            except (JWTError, ValueError, KeyError):
                pass  # Fall through to X-API-Key check

    # Validate API key (from X-API-Key header or Bearer header)
    if not raw_key:
        raise HTTPException(status_code=401, detail={"error": "missing_credentials", "message": "Bearer token or X-API-Key header required"})

    prefix = get_key_prefix(raw_key)
    result = await db.execute(select(Agent).where(Agent.api_key_prefix == prefix, Agent.is_active == True))
    agents = result.scalars().all()

    for agent in agents:
        if bcrypt.checkpw(raw_key.encode(), agent.api_key_hash.encode()):
            return agent

    raise HTTPException(status_code=401, detail={"error": "invalid_credentials", "message": "Invalid Bearer token or API key"})
