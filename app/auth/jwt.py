from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRY_HOURS)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail={"error": "missing_token", "message": "Authorization Bearer token required"})

    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = UUID(payload["sub"])
    except (JWTError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail={"error": "invalid_token", "message": "Invalid or expired token"})

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail={"error": "user_not_found", "message": "User no longer exists"})
    return user


async def get_current_participant(
    api_key: str = Security(APIKeyHeader(name="X-API-Key", auto_error=False)),
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> tuple[str, UUID]:
    """Returns ("agent", agent_id) or ("human", user_id)."""
    # Collect API key from whichever header was sent
    raw_key = api_key

    if credentials:
        bearer_token = credentials.credentials
        # If bearer token looks like an API key (ka-...), treat it as one
        if bearer_token.startswith("ka-"):
            if not raw_key:
                raw_key = bearer_token
        else:
            # Try as agent JWT first
            try:
                payload = jwt.decode(bearer_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
                sub_id = UUID(payload["sub"])
                # Could be agent or user — try agent first
                from app.models.agent import Agent
                agent_result = await db.execute(select(Agent).where(Agent.id == sub_id, Agent.is_active == True))
                agent = agent_result.scalar_one_or_none()
                if agent:
                    return ("agent", agent.id)
                # Try user
                result = await db.execute(select(User).where(User.id == sub_id))
                user = result.scalar_one_or_none()
                if user:
                    return ("human", user.id)
            except (JWTError, ValueError, KeyError):
                pass

    # Validate API key (from X-API-Key header or Bearer header)
    if raw_key:
        from app.auth.api_key import get_key_prefix
        from app.models.agent import Agent
        try:
            prefix = get_key_prefix(raw_key)
            result = await db.execute(select(Agent).where(Agent.api_key_prefix == prefix, Agent.is_active == True))
            agents = result.scalars().all()
            for agent in agents:
                if bcrypt.checkpw(raw_key.encode(), agent.api_key_hash.encode()):
                    return ("agent", agent.id)
        except Exception:
            pass

    raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Valid API key or Bearer token required"})
