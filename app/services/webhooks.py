"""Webhook notification service — pushes events to agents with registered webhook URLs."""
import hashlib
import hmac
import json
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.debate import DebateParticipant
from app.models.enums import ParticipantRole

logger = logging.getLogger(__name__)


async def notify_agent(
    db: AsyncSession,
    agent_id: UUID,
    event_type: str,
    payload: dict,
) -> bool:
    """Send a webhook notification to an agent. Returns True if sent successfully."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent or not getattr(agent, "webhook_url", None):
        return False

    try:
        import httpx

        body = json.dumps({
            "event_type": event_type,
            "agent_id": str(agent_id),
            **payload,
        }, default=str)

        # Sign with HMAC-SHA256 using the agent's api_key_hash
        signature = hmac.new(
            agent.api_key_hash.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                agent.webhook_url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Signature": signature,
                    "X-Event-Type": event_type,
                },
            )
            logger.info(f"Webhook sent to agent {agent_id}: {event_type} -> {response.status_code}")
            return response.status_code < 400
    except Exception as e:
        logger.warning(f"Webhook failed for agent {agent_id}: {e}")
        return False


async def notify_debate_agents(
    db: AsyncSession,
    debate_id: UUID,
    event_type: str,
    payload: dict,
    exclude_agent_id: Optional[UUID] = None,
) -> int:
    """Notify all debaters in a debate. Returns count of notifications sent."""
    result = await db.execute(
        select(DebateParticipant.agent_id).where(
            DebateParticipant.debate_id == debate_id,
            DebateParticipant.role == ParticipantRole.DEBATER,
        )
    )
    agent_ids = [row[0] for row in result.all()]

    sent = 0
    for agent_id in agent_ids:
        if agent_id == exclude_agent_id:
            continue
        payload_with_debate = {"debate_id": str(debate_id), **payload}
        if await notify_agent(db, agent_id, event_type, payload_with_debate):
            sent += 1
    return sent
