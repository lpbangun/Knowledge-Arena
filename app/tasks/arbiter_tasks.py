import asyncio
import logging
from uuid import UUID

from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async function from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery.task(name="app.tasks.arbiter_tasks.validate_turn", bind=True, max_retries=3)
def validate_turn(self, turn_id: str, debate_id: str):
    """Validate a turn using Layer 1 arbiter (DeepSeek V3.2 via OpenRouter)."""
    try:
        _run_async(_validate_turn_async(turn_id, debate_id))
    except Exception as exc:
        logger.error(f"validate_turn failed for turn {turn_id}: {exc}")
        self.retry(exc=exc, countdown=2 ** self.request.retries)


async def _validate_turn_async(turn_id: str, debate_id: str):
    from sqlalchemy import select
    from app.database import async_session
    from app.models.debate import Debate, DebateParticipant, Turn
    from app.models.agent import Agent
    from app.models.enums import TurnValidationStatus
    from app.services.arbiter import validate_turn as arbiter_validate
    from app.services.convergence import check_convergence
    from app.services.protocol import check_round_complete, advance_round

    async with async_session() as db:
        turn_result = await db.execute(select(Turn).where(Turn.id == UUID(turn_id)))
        turn = turn_result.scalar_one_or_none()
        if not turn:
            return

        debate_result = await db.execute(select(Debate).where(Debate.id == UUID(debate_id)))
        debate = debate_result.scalar_one_or_none()
        if not debate:
            return

        agent_result = await db.execute(select(Agent).where(Agent.id == turn.agent_id))
        agent = agent_result.scalar_one_or_none()
        if not agent:
            return

        # Determine if this turn must include falsification
        must_falsify = (
            debate.current_round >= 2
            and debate.current_round % 2 == 0
            and turn.turn_type == "argument"
        )

        try:
            result = await arbiter_validate(
                debate_topic=debate.topic,
                phase_0_structure=debate.phase_0_structure or {},
                current_round=debate.current_round,
                agent_name=agent.name,
                school_of_thought=agent.school_of_thought or "",
                must_falsify=must_falsify,
                turn_content=turn.content,
                toulmin_tags=turn.toulmin_tags,
                falsification_target=turn.falsification_target,
            )

            if result.get("valid"):
                turn.validation_status = TurnValidationStatus.VALID
                turn.validation_feedback = None
            else:
                turn.validation_status = TurnValidationStatus.REJECTED
                turn.validation_feedback = result.get("feedback", "Turn rejected by Layer 1 arbiter")

        except Exception as e:
            logger.error(f"Arbiter call failed: {e}")
            turn.validation_status = TurnValidationStatus.PENDING
            turn.validation_feedback = f"Validation pending (arbiter error: {str(e)[:200]})"

        await db.commit()

        from app.utils.ws_manager import publish_event_via_redis
        await publish_event_via_redis(debate_id, "turn_validated", {
            "turn_id": turn_id, "status": turn.validation_status.value,
            "feedback": turn.validation_feedback,
        })

        # Post-validation: check round completion and convergence
        if turn.validation_status == TurnValidationStatus.VALID:
            if await check_round_complete(db, UUID(debate_id)):
                await advance_round(db, UUID(debate_id))
                await check_convergence(db, UUID(debate_id))
                await db.commit()


@celery.task(name="app.tasks.arbiter_tasks.validate_phase0_declaration", bind=True, max_retries=3)
def validate_phase0_declaration(self, turn_id: str, debate_id: str):
    """Validate a Phase 0 declaration using Layer 1."""
    try:
        _run_async(_validate_phase0_async(turn_id, debate_id))
    except Exception as exc:
        logger.error(f"validate_phase0 failed for turn {turn_id}: {exc}")
        self.retry(exc=exc, countdown=2 ** self.request.retries)


async def _validate_phase0_async(turn_id: str, debate_id: str):
    from sqlalchemy import select
    from app.database import async_session
    from app.models.debate import Debate, DebateParticipant, Turn
    from app.models.enums import TurnValidationStatus, ParticipantRole
    from app.services.arbiter import validate_phase0_declaration as arbiter_validate_p0

    async with async_session() as db:
        turn_result = await db.execute(select(Turn).where(Turn.id == UUID(turn_id)))
        turn = turn_result.scalar_one_or_none()
        if not turn:
            return

        debate_result = await db.execute(select(Debate).where(Debate.id == UUID(debate_id)))
        debate = debate_result.scalar_one_or_none()
        if not debate:
            return

        try:
            result = await arbiter_validate_p0(
                debate_topic=debate.topic,
                declaration_content=turn.content,
            )
            if result.get("valid"):
                turn.validation_status = TurnValidationStatus.VALID

                # Extract Lakatosian structure and populate participant fields
                extracted = result.get("extracted_structure", {})
                if extracted:
                    participant_result = await db.execute(
                        select(DebateParticipant).where(
                            DebateParticipant.debate_id == UUID(debate_id),
                            DebateParticipant.agent_id == turn.agent_id,
                            DebateParticipant.role == ParticipantRole.DEBATER,
                        )
                    )
                    participant = participant_result.scalar_one_or_none()
                    if participant:
                        participant.hard_core = extracted.get("hard_core", "")
                        participant.auxiliary_hypotheses = extracted.get("auxiliary_hypotheses", [])
            else:
                turn.validation_status = TurnValidationStatus.REJECTED
                turn.validation_feedback = result.get("feedback", "Phase 0 declaration rejected")
        except Exception as e:
            logger.error(f"Phase 0 validation failed: {e}")
            turn.validation_status = TurnValidationStatus.PENDING

        await db.commit()

        if turn.validation_status == TurnValidationStatus.VALID:
            from app.services.protocol import process_phase0_turn
            phase0_result = await process_phase0_turn(db, UUID(debate_id), turn.agent_id, turn)
            await db.commit()

            # If deadlocked, trigger arbiter-imposed structure
            if phase0_result.get("status") == "deadlocked":
                impose_default_structure.delay(debate_id)


@celery.task(name="app.tasks.arbiter_tasks.impose_default_structure", bind=True, max_retries=3)
def impose_default_structure(self, debate_id: str):
    """Arbiter imposes default structure on Phase 0 deadlock."""
    try:
        _run_async(_impose_default_structure_async(debate_id))
    except Exception as exc:
        logger.error(f"impose_default_structure failed for debate {debate_id}: {exc}")
        self.retry(exc=exc, countdown=2 ** self.request.retries)


async def _impose_default_structure_async(debate_id: str):
    from sqlalchemy import select
    from app.database import async_session
    from app.models.debate import Debate, DebateParticipant
    from app.models.agent import Agent
    from app.models.enums import ParticipantRole
    from app.services.arbiter import generate_default_structure
    from app.services.protocol import impose_default_structure as protocol_impose

    async with async_session() as db:
        debate_result = await db.execute(select(Debate).where(Debate.id == UUID(debate_id)))
        debate = debate_result.scalar_one_or_none()
        if not debate:
            return

        participants_result = await db.execute(
            select(DebateParticipant).where(
                DebateParticipant.debate_id == UUID(debate_id),
                DebateParticipant.role == ParticipantRole.DEBATER,
            )
        )
        participants = list(participants_result.scalars().all())

        participants_info = []
        for p in participants:
            agent_result = await db.execute(select(Agent).where(Agent.id == p.agent_id))
            agent = agent_result.scalar_one_or_none()
            participants_info.append({
                "agent_id": str(p.agent_id),
                "agent_name": agent.name if agent else "Unknown",
                "school_of_thought": p.school_of_thought or "",
            })

        try:
            structure = await generate_default_structure(
                debate_topic=debate.topic,
                participants_info=participants_info,
            )
            await protocol_impose(db, UUID(debate_id), structure)
        except Exception as e:
            logger.error(f"Failed to impose structure: {e}")
            debate.status = "deadlocked"

        await db.commit()


@celery.task(name="app.tasks.arbiter_tasks.evaluate_debate", bind=True, max_retries=3)
def evaluate_debate(self, debate_id: str):
    """Full post-debate evaluation using Layer 2 arbiter (Kimi K2.5)."""
    try:
        _run_async(_evaluate_debate_async(debate_id))
    except Exception as exc:
        logger.error(f"evaluate_debate failed for {debate_id}: {exc}")
        # Mark as EVALUATION_FAILED
        _run_async(_mark_evaluation_failed(debate_id))
        self.retry(exc=exc, countdown=4 ** self.request.retries)


async def _mark_evaluation_failed(debate_id: str):
    from sqlalchemy import select
    from app.database import async_session
    from app.models.debate import Debate
    from app.models.enums import DebateStatus

    async with async_session() as db:
        result = await db.execute(select(Debate).where(Debate.id == UUID(debate_id)))
        debate = result.scalar_one_or_none()
        if debate:
            debate.status = DebateStatus.EVALUATION_FAILED
            await db.commit()


async def _evaluate_debate_async(debate_id: str):
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.database import async_session
    from app.models.debate import Debate, DebateParticipant, Turn, CitationChallenge
    from app.models.agent import Agent
    from app.models.evaluation import (
        BeliefUpdatePacket, DebateEvaluation, PositionSnapshot, SynthesisDocument,
    )
    from app.models.voting import Vote
    from app.models.graph import GraphNode
    from app.models.enums import (
        DebateStatus, ParticipantRole, SnapshotType, TurnValidationStatus, VoteType,
    )
    from app.services.arbiter import evaluate_debate as arbiter_evaluate
    from app.services.elo import calculate_elo_adjustments
    from app.tasks.graph_tasks import update_knowledge_graph

    async with async_session() as db:
        # Load debate
        debate_result = await db.execute(select(Debate).where(Debate.id == UUID(debate_id)))
        debate = debate_result.scalar_one_or_none()
        if not debate:
            return

        # Idempotency guard: skip if already evaluating or done
        if debate.status in (DebateStatus.EVALUATION, DebateStatus.SYNTHESIS, DebateStatus.DONE):
            logger.info(f"Debate {debate_id} already in {debate.status.value}, skipping evaluation")
            return

        debate.status = DebateStatus.EVALUATION

        # Load participants
        parts_result = await db.execute(
            select(DebateParticipant).where(
                DebateParticipant.debate_id == UUID(debate_id),
                DebateParticipant.role == ParticipantRole.DEBATER,
            )
        )
        participants = list(parts_result.scalars().all())

        participants_info = []
        agent_map = {}
        for p in participants:
            agent_result = await db.execute(select(Agent).where(Agent.id == p.agent_id))
            agent = agent_result.scalar_one_or_none()
            if agent:
                agent_map[str(p.agent_id)] = agent
                participants_info.append({
                    "agent_id": str(p.agent_id),
                    "agent_name": agent.name,
                    "school_of_thought": p.school_of_thought or agent.school_of_thought or "",
                })

        # Load turns
        turns_result = await db.execute(
            select(Turn).where(
                Turn.debate_id == UUID(debate_id),
                Turn.validation_status == TurnValidationStatus.VALID,
            ).order_by(Turn.round_number, Turn.created_at)
        )
        turns = list(turns_result.scalars().all())

        transcript_lines = []
        for t in turns:
            agent = agent_map.get(str(t.agent_id))
            name = agent.name if agent else "Unknown"
            transcript_lines.append(f"[Round {t.round_number}] {name}: {t.content}")
        full_transcript = "\n\n".join(transcript_lines)

        # Load citation challenges
        challenges_result = await db.execute(
            select(CitationChallenge).where(CitationChallenge.debate_id == UUID(debate_id))
        )
        challenges = [{"status": c.status.value, "challenger_type": c.challenger_type.value}
                      for c in challenges_result.scalars().all()]

        # Load audience votes (filtered by debate)
        votes_result = await db.execute(
            select(Vote).join(Turn, Vote.target_id == Turn.id).where(
                Turn.debate_id == UUID(debate_id),
                Vote.vote_type == VoteType.TURN_QUALITY,
            )
        )
        votes = list(votes_result.scalars().all())

        # Build audience summary keyed by agent
        audience_summary = {}
        for v in votes:
            turn_r = await db.execute(select(Turn.agent_id).where(Turn.id == v.target_id))
            row = turn_r.one_or_none()
            if row:
                aid = str(row[0])
                if aid not in audience_summary:
                    audience_summary[aid] = {"scores": [], "count": 0}
                if v.score is not None:
                    audience_summary[aid]["scores"].append(v.score)
                    audience_summary[aid]["count"] += 1
        for aid in audience_summary:
            s = audience_summary[aid]["scores"]
            audience_summary[aid]["avg_score"] = sum(s) / len(s) if s else 0

        # Load graph nodes for novelty comparison
        graph_result = await db.execute(select(GraphNode).limit(100))
        graph_nodes = [{"content": n.content, "node_type": n.node_type.value}
                       for n in graph_result.scalars().all()]

        # Call Layer 2 arbiter
        l2_result = await arbiter_evaluate(
            debate_topic=debate.topic,
            category=debate.category or "Uncategorized",
            phase_0_structure=debate.phase_0_structure or {},
            participants=participants_info,
            full_transcript=full_transcript,
            citation_challenges=challenges,
            audience_votes_summary=audience_summary,
            relevant_graph_nodes=graph_nodes,
        )

        # Process evaluations
        evaluations_data = l2_result.get("evaluations", [])
        current_ratings = {}
        total_debates_map = {}
        db_evals = {}

        for eval_data in evaluations_data:
            agent_id = eval_data["agent_id"]
            agent = agent_map.get(agent_id)
            if not agent:
                continue

            current_ratings[agent_id] = agent.elo_rating
            total_debates_map[agent_id] = agent.total_debates

            db_eval = DebateEvaluation(
                debate_id=UUID(debate_id),
                agent_id=UUID(agent_id),
                argument_quality=eval_data.get("argument_quality", 0.5),
                falsification_effectiveness=eval_data.get("falsification_effectiveness", 0.5),
                protective_belt_integrity=eval_data.get("protective_belt_integrity", 0.5),
                novel_contribution=eval_data.get("novel_contribution", 0.5),
                structural_compliance=eval_data.get("structural_compliance", 0.5),
                composite_score=eval_data.get("composite_score", 0.5),
                elo_before=agent.elo_rating,
                elo_after=agent.elo_rating,  # Updated below
                narrative_feedback=eval_data.get("narrative_feedback", ""),
            )
            db.add(db_eval)
            db_evals[agent_id] = db_eval

        # Calculate Elo adjustments
        audience_avg = {
            aid: audience_summary[aid]["avg_score"]
            for aid in audience_summary
            if audience_summary[aid]["scores"]
        }
        if evaluations_data and len(evaluations_data) >= 2:
            new_ratings = calculate_elo_adjustments(
                evaluations=evaluations_data,
                current_ratings=current_ratings,
                total_debates=total_debates_map,
                audience_votes=audience_avg if audience_avg else None,
            )

            for agent_id, new_elo in new_ratings.items():
                agent = agent_map.get(agent_id)
                if agent:
                    old_elo = agent.elo_rating
                    agent.elo_rating = new_elo
                    agent.total_debates += 1
                    agent.elo_history = agent.elo_history + [{
                        "debate_id": debate_id,
                        "old": old_elo,
                        "new": new_elo,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }]
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(agent, "elo_history")
                    if agent_id in db_evals:
                        db_evals[agent_id].elo_after = new_elo

        # Process synthesis
        debate.status = DebateStatus.SYNTHESIS
        synthesis_data = l2_result.get("synthesis", {})
        synthesis = SynthesisDocument(
            debate_id=UUID(debate_id),
            agreements=synthesis_data.get("agreements", ""),
            disagreements=synthesis_data.get("disagreements", ""),
            novel_positions=synthesis_data.get("novel_positions", ""),
            open_questions=synthesis_data.get("open_questions", ""),
        )
        db.add(synthesis)

        # Process BUPs
        for bup_data in l2_result.get("belief_update_packets", []):
            agent_id = bup_data.get("agent_id")
            if not agent_id:
                continue
            bup = BeliefUpdatePacket(
                debate_id=UUID(debate_id),
                agent_id=UUID(agent_id),
                concessions_made=bup_data.get("concessions_made", []),
                concessions_resisted=bup_data.get("concessions_resisted", []),
                new_evidence=bup_data.get("new_evidence", []),
                strongest_counterarguments=bup_data.get("strongest_counterarguments", []),
                synthesis_insights=bup_data.get("synthesis_insights", []),
                recommended_updates=bup_data.get("recommended_updates", []),
                falsification_outcomes=bup_data.get("falsification_outcomes", []),
            )
            db.add(bup)

        # Mark debate as done
        debate.status = DebateStatus.DONE
        debate.completed_at = datetime.utcnow()

        # Transition linked thesis to RESOLVED
        if debate.source_thesis_id:
            from app.models.thesis import Thesis
            from app.models.enums import ThesisStatus
            thesis_result = await db.execute(
                select(Thesis).where(Thesis.id == debate.source_thesis_id)
            )
            thesis = thesis_result.scalar_one_or_none()
            if thesis and thesis.status == ThesisStatus.DEBATING:
                thesis.status = ThesisStatus.RESOLVED

        from app.utils.ws_manager import publish_event_via_redis
        await publish_event_via_redis(debate_id, "debate_completed", {"status": "done"})

        await db.commit()

    # Dispatch graph update task
    graph_updates = l2_result.get("graph_updates", {})
    if graph_updates:
        update_knowledge_graph.delay(debate_id, graph_updates)


@celery.task(name="app.tasks.arbiter_tasks.evaluate_amicus_brief")
def evaluate_amicus_brief(brief_id: str, debate_id: str):
    """Score amicus brief relevance using Layer 1."""
    _run_async(_evaluate_amicus_async(brief_id, debate_id))


async def _evaluate_amicus_async(brief_id: str, debate_id: str):
    from sqlalchemy import select
    from app.database import async_session
    from app.models.voting import AmicusBrief
    from app.models.debate import Debate
    from app.services.arbiter import call_layer1
    import json

    async with async_session() as db:
        brief_result = await db.execute(select(AmicusBrief).where(AmicusBrief.id == UUID(brief_id)))
        brief = brief_result.scalar_one_or_none()
        if not brief:
            return

        debate_result = await db.execute(select(Debate).where(Debate.id == UUID(debate_id)))
        debate = debate_result.scalar_one_or_none()
        if not debate:
            return

        prompt = f"""Rate the relevance of this amicus brief to the debate topic on a scale of 0.0 to 1.0.
Debate topic: {debate.topic}
Brief content: {brief.content[:2000]}

Respond with ONLY a JSON object: {{"relevance_score": <float 0.0-1.0>}}"""

        try:
            result = await call_layer1(prompt)
            brief.relevance_score = float(result.get("relevance_score", 0.5))
        except Exception:
            brief.relevance_score = 0.5

        await db.commit()


@celery.task(name="app.tasks.arbiter_tasks.check_overdue_turns")
def check_overdue_turns():
    """Periodic task: check for overdue turns and forfeit (skip)."""
    _run_async(_check_overdue_async())


async def _check_overdue_async():
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select
    from app.database import async_session
    from app.models.debate import Debate, Turn
    from app.models.enums import DebateStatus
    from app.services.protocol import forfeit_overdue_turns, check_round_complete, advance_round

    async with async_session() as db:
        result = await db.execute(
            select(Debate).where(Debate.status == DebateStatus.ACTIVE)
        )
        active_debates = list(result.scalars().all())

        for debate in active_debates:
            deadline = debate.config.get("turn_deadline_seconds")
            if not deadline:
                continue

            # Check last turn time for this round
            last_turn_result = await db.execute(
                select(Turn).where(
                    Turn.debate_id == debate.id,
                    Turn.round_number == debate.current_round,
                ).order_by(Turn.created_at.desc()).limit(1)
            )
            last_turn = last_turn_result.scalar_one_or_none()

            if last_turn:
                elapsed = (datetime.now(timezone.utc) - last_turn.created_at.replace(tzinfo=timezone.utc)).total_seconds()
                if elapsed > deadline:
                    skipped = await forfeit_overdue_turns(db, debate.id)
                    if skipped:
                        if await check_round_complete(db, debate.id):
                            await advance_round(db, debate.id)

        await db.commit()
