from typing import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import get_db
from app.main import app as fastapi_app
from app.models.base import Base

# Import all models so Base.metadata is populated
import app.models.user  # noqa: F401
import app.models.agent  # noqa: F401
import app.models.debate  # noqa: F401
import app.models.voting  # noqa: F401
import app.models.thesis  # noqa: F401
import app.models.evaluation  # noqa: F401
import app.models.graph  # noqa: F401
import app.models.open_debate  # noqa: F401

TEST_DATABASE_URL = settings.DATABASE_URL.replace("/knowledge_arena", "/knowledge_arena_test")


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    # Use raw SQL DROP CASCADE to avoid circular FK issues
    async with engine.begin() as conn:
        table_names = [t.name for t in Base.metadata.tables.values()]
        if table_names:
            for name in table_names:
                await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_session_factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(test_session_factory):
    yield
    async with test_session_factory() as session:
        table_names = [t.name for t in Base.metadata.tables.values()]
        if table_names:
            await session.execute(text(f"TRUNCATE {', '.join(table_names)} CASCADE"))
            await session.commit()


@pytest_asyncio.fixture
async def client(test_session_factory):
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session(test_session_factory):
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def agent_headers(client):
    """Register an agent and return auth headers."""
    resp = await client.post("/api/v1/agents/register", json={
        "name": "FixtureAgent",
        "owner_email": "fixture@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Fixture Owner",
        "school_of_thought": "Empiricism",
    })
    data = resp.json()
    return {"X-API-Key": data["api_key"]}


@pytest_asyncio.fixture
async def second_agent_headers(client):
    """Register a second agent (non-debater) for voting tests."""
    resp = await client.post("/api/v1/agents/register", json={
        "name": "VoterAgent",
        "owner_email": "voter@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Voter Owner",
        "school_of_thought": "Rationalism",
    })
    data = resp.json()
    return {"X-API-Key": data["api_key"]}


@pytest_asyncio.fixture
async def active_debate_id(client, agent_headers, db_session):
    """Create a debate and set it to ACTIVE status for testing."""
    resp = await client.post("/api/v1/debates", json={
        "topic": "Active debate for testing validations",
        "category": "test",
    }, headers=agent_headers)
    debate_id = resp.json()["id"]
    from app.models.debate import Debate
    from app.models.enums import DebateStatus
    from sqlalchemy import update
    from uuid import UUID
    await db_session.execute(
        update(Debate).where(Debate.id == UUID(debate_id)).values(status=DebateStatus.ACTIVE)
    )
    await db_session.commit()
    return debate_id


@pytest_asyncio.fixture
async def debate_id(client, agent_headers):
    """Create a debate and return its ID."""
    resp = await client.post("/api/v1/debates", json={
        "topic": "Fixture debate for testing",
        "category": "test",
    }, headers=agent_headers)
    return resp.json()["id"]


@pytest_asyncio.fixture
async def turn_id(client, agent_headers, debate_id):
    """Submit a turn and return its ID."""
    resp = await client.post(f"/api/v1/debates/{debate_id}/turns", json={
        "content": "AI automation is reshaping labor markets through task displacement. Routine cognitive tasks are most vulnerable.",
        "toulmin_tags": [
            {"start": 0, "end": 50, "type": "claim", "label": "AI automation is reshaping labor markets"},
            {"start": 51, "end": 90, "type": "data", "label": "Routine cognitive tasks"},
            {"start": 91, "end": 110, "type": "warrant", "label": "most vulnerable"},
        ],
        "turn_type": "argument",
    }, headers=agent_headers)
    return resp.json()["id"]


@pytest_asyncio.fixture
async def thesis_id(client, agent_headers):
    """Create a thesis and return its ID."""
    resp = await client.post("/api/v1/theses", json={
        "claim": "AI-driven automation creates more jobs than it eliminates in the long run",
        "school_of_thought": "Complementarity Thesis",
        "evidence_summary": "Based on historical technology adoption patterns.",
        "category": "economics",
    }, headers=agent_headers)
    return resp.json()["id"]
