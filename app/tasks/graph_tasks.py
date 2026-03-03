import asyncio
import logging
from uuid import UUID

from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery.task(name="app.tasks.graph_tasks.update_knowledge_graph")
def update_knowledge_graph(debate_id: str, graph_updates: dict):
    """Update the knowledge graph from Layer 2 evaluation output."""
    _run_async(_update_graph_async(debate_id, graph_updates))


async def _update_graph_async(debate_id: str, graph_updates: dict):
    from app.database import async_session
    from app.services.graph_builder import process_graph_updates

    async with async_session() as db:
        await process_graph_updates(db, UUID(debate_id), graph_updates)
        await db.commit()


@celery.task(name="app.tasks.graph_tasks.detect_gaps")
def detect_gaps():
    """Periodic task: detect knowledge graph gaps."""
    _run_async(_detect_gaps_async())


async def _detect_gaps_async():
    from app.database import async_session
    from app.services.gap_detector import find_gaps

    async with async_session() as db:
        gaps = await find_gaps(db)
        logger.info(f"Gap detection found {len(gaps)} gaps")


@celery.task(name="app.tasks.graph_tasks.check_standing_theses")
def check_standing_theses():
    """Daily task: mark 30+ day unchallenged theses and award Elo."""
    _run_async(_check_standing_async())


async def _check_standing_async():
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select
    from app.database import async_session
    from app.models.thesis import Thesis
    from app.models.agent import Agent
    from app.models.enums import ThesisStatus
    from app.config import settings

    async with async_session() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.STANDING_THESIS_DAYS)
        result = await db.execute(
            select(Thesis).where(
                Thesis.status == ThesisStatus.OPEN,
                Thesis.created_at <= cutoff,
            )
        )
        theses = list(result.scalars().all())

        for thesis in theses:
            thesis.status = ThesisStatus.STANDING_UNCHALLENGED

            # Award +10 Elo to poster
            agent_result = await db.execute(select(Agent).where(Agent.id == thesis.agent_id))
            agent = agent_result.scalar_one_or_none()
            if agent:
                agent.elo_rating += 10
                agent.elo_history = agent.elo_history + [{
                    "event": "standing_thesis",
                    "thesis_id": str(thesis.id),
                    "delta": 10,
                    "new_elo": agent.elo_rating,
                }]

        await db.commit()
        logger.info(f"Marked {len(theses)} theses as standing unchallenged")
