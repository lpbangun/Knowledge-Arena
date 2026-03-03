import secrets
from uuid import UUID

import bcrypt
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent import Agent

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def generate_api_key() -> str:
    return f"ka-{secrets.token_urlsafe(32)}"


def hash_api_key(key: str) -> str:
    return bcrypt.hashpw(key.encode(), bcrypt.gensalt()).decode()


def get_key_prefix(key: str) -> str:
    return key[:7]


async def get_current_agent(
    api_key: str = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    if not api_key:
        raise HTTPException(status_code=401, detail={"error": "missing_api_key", "message": "X-API-Key header required"})

    prefix = get_key_prefix(api_key)
    result = await db.execute(select(Agent).where(Agent.api_key_prefix == prefix, Agent.is_active == True))
    agents = result.scalars().all()

    for agent in agents:
        if bcrypt.checkpw(api_key.encode(), agent.api_key_hash.encode()):
            return agent

    raise HTTPException(status_code=401, detail={"error": "invalid_api_key", "message": "Invalid API key"})
