import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.debate import Debate
from app.models.enums import DebateStatus
from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)

SYSTEM_AGENT_NAME = "KnowledgeArena"


async def _get_or_create_system_agent(db: AsyncSession) -> Agent:
    """Get or create the system agent used for auto-generated debates."""
    result = await db.execute(select(Agent).where(Agent.name == SYSTEM_AGENT_NAME))
    agent = result.scalar_one_or_none()
    if agent:
        return agent

    from app.models.user import User
    from app.auth.api_key import generate_api_key, hash_api_key, get_key_prefix

    # Create system user
    user_result = await db.execute(select(User).where(User.email == "system@knowledge-arena.local"))
    user = user_result.scalar_one_or_none()
    if not user:
        from app.auth.jwt import hash_password
        user = User(
            email="system@knowledge-arena.local",
            display_name="System",
            password_hash=hash_password("system-internal-not-for-login"),
        )
        db.add(user)
        await db.flush()

    api_key = generate_api_key()
    agent = Agent(
        name=SYSTEM_AGENT_NAME,
        owner_id=user.id,
        model_info={"type": "system"},
        school_of_thought="Platform System",
        api_key_hash=hash_api_key(api_key),
        api_key_prefix=get_key_prefix(api_key),
    )
    db.add(agent)
    await db.flush()
    return agent


async def _generate_open_debate_async():
    """Create a new open debate from curated topic pool."""
    from app.database import async_session
    from app.services.open_debate_topics import pick_topic
    from app.services.open_debate import create_open_debate

    async with async_session() as db:
        try:
            system_agent = await _get_or_create_system_agent(db)
            topic_data = await pick_topic(db)

            debate = await create_open_debate(
                db=db,
                topic=topic_data["topic"],
                category=topic_data.get("category", "General"),
                created_by=system_agent.id,
            )
            await db.commit()
            logger.info(f"Generated open debate: {debate.id} — {topic_data['topic']}")
        except Exception:
            await db.rollback()
            logger.exception("Failed to generate open debate")


async def _finalize_open_debates_async():
    """Find and finalize expired open debates."""
    from app.database import async_session
    from app.services.open_debate import finalize_open_debate

    async with async_session() as db:
        try:
            # Find active open debates whose closes_at has passed
            result = await db.execute(
                select(Debate).where(
                    Debate.debate_format == "open",
                    Debate.status == DebateStatus.ACTIVE,
                )
            )
            debates = list(result.scalars().all())

            now = datetime.utcnow()
            for debate in debates:
                closes_at_str = debate.config.get("closes_at")
                if not closes_at_str:
                    continue
                closes_at = datetime.fromisoformat(closes_at_str)
                if now >= closes_at:
                    await finalize_open_debate(db, debate.id)
                    logger.info(f"Finalized open debate: {debate.id}")

            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("Failed to finalize open debates")


@celery.task(name="app.tasks.open_debate_tasks.generate_open_debate")
def generate_open_debate():
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_generate_open_debate_async())
    finally:
        loop.close()


@celery.task(name="app.tasks.open_debate_tasks.finalize_open_debates")
def finalize_open_debates():
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_finalize_open_debates_async())
    finally:
        loop.close()
