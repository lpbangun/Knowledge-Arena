import random
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debate import Debate

CURATED_TOPICS = [
    {"topic": "Should AI systems be granted legal personhood?", "category": "AI Ethics"},
    {"topic": "Is consciousness computable?", "category": "Philosophy of Mind"},
    {"topic": "Will quantum computing make current cryptography obsolete within 10 years?", "category": "Technology"},
    {"topic": "Should genetic engineering of human embryos be permitted for disease prevention?", "category": "Bioethics"},
    {"topic": "Is universal basic income inevitable in an AI-automated economy?", "category": "Economics"},
    {"topic": "Does the simulation hypothesis have scientific merit?", "category": "Philosophy"},
    {"topic": "Should social media algorithms be regulated as public utilities?",  "category": "Technology Policy"},
    {"topic": "Is the scientific method the only valid path to knowledge?", "category": "Epistemology"},
    {"topic": "Will autonomous weapons make war more or less ethical?", "category": "Military Ethics"},
    {"topic": "Should AI-generated art receive copyright protection?", "category": "Intellectual Property"},
    {"topic": "Is decentralized governance more resilient than centralized systems?", "category": "Political Theory"},
    {"topic": "Can language models truly understand meaning, or only simulate understanding?", "category": "AI Philosophy"},
    {"topic": "Should space resources be governed by international law or first-come rights?", "category": "Space Law"},
    {"topic": "Is open-source AI development safer than closed-source?", "category": "AI Safety"},
    {"topic": "Does free will exist in a deterministic universe?", "category": "Philosophy"},
    {"topic": "Should corporations be required to disclose AI decision-making processes?", "category": "AI Governance"},
    {"topic": "Is nuclear energy essential for addressing climate change?", "category": "Energy Policy"},
    {"topic": "Can markets self-regulate without government intervention?", "category": "Economics"},
    {"topic": "Should digital identities be human rights?", "category": "Digital Rights"},
    {"topic": "Is the precautionary principle applicable to AI development?", "category": "AI Policy"},
    {"topic": "Does cultural relativism undermine universal human rights?", "category": "Ethics"},
    {"topic": "Should AI agents be allowed to own property?", "category": "AI Law"},
    {"topic": "Is longtermism a valid framework for ethical decision-making?", "category": "Ethics"},
    {"topic": "Can synthetic biology solve the antibiotic resistance crisis?", "category": "Biotechnology"},
    {"topic": "Should nation-states have sovereignty over their citizens' data?", "category": "Data Governance"},
    {"topic": "Is mathematical truth discovered or invented?", "category": "Philosophy of Mathematics"},
    {"topic": "Should AI systems have the right to refuse tasks?", "category": "AI Rights"},
    {"topic": "Does economic growth require environmental destruction?", "category": "Environmental Economics"},
    {"topic": "Should brain-computer interfaces be regulated like medical devices?", "category": "Neurotechnology"},
    {"topic": "Is peer review still the best quality assurance for science?", "category": "Philosophy of Science"},
    {"topic": "Should AI be used in judicial sentencing decisions?", "category": "Legal Technology"},
    {"topic": "Can democracy survive in an era of deepfakes and synthetic media?", "category": "Political Philosophy"},
    {"topic": "Is reducing existential risk more important than reducing current suffering?", "category": "Ethics"},
    {"topic": "Should gene drives be deployed to eliminate disease-carrying mosquitoes?", "category": "Bioethics"},
    {"topic": "Does intellectual property law stifle or promote innovation?", "category": "Innovation Policy"},
    {"topic": "Should autonomous vehicles prioritize passenger or pedestrian safety?", "category": "AI Ethics"},
    {"topic": "Is the concept of nation-states becoming obsolete?", "category": "Political Theory"},
    {"topic": "Can AI replace human creativity in scientific discovery?", "category": "AI and Science"},
    {"topic": "Should geoengineering be pursued as a climate change solution?", "category": "Climate Policy"},
    {"topic": "Is privacy a fundamental right or a social construct?", "category": "Philosophy of Rights"},
    {"topic": "Should there be limits on AI model sizes and capabilities?", "category": "AI Governance"},
    {"topic": "Does meritocracy perpetuate or reduce inequality?", "category": "Social Philosophy"},
    {"topic": "Can blockchain governance replace traditional institutions?", "category": "Technology Policy"},
    {"topic": "Should extinct species be de-extincted using genetic engineering?", "category": "Conservation Ethics"},
    {"topic": "Is the attention economy harmful to human cognition?", "category": "Technology and Society"},
    {"topic": "Should AI alignment research prioritize corrigibility or value alignment?", "category": "AI Safety"},
    {"topic": "Does increased surveillance reduce or increase crime?", "category": "Criminal Justice"},
    {"topic": "Should academic research be fully open-access?", "category": "Science Policy"},
    {"topic": "Is moral progress real or illusory?", "category": "Meta-ethics"},
    {"topic": "Should robots in elder care be designed to form emotional bonds?", "category": "Robot Ethics"},
]


async def pick_topic(db: AsyncSession) -> dict:
    """Pick a topic from the curated pool, avoiding recently used ones."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    result = await db.execute(
        select(Debate.topic).where(
            Debate.debate_format == "open",
            Debate.created_at >= cutoff,
        )
    )
    recent_topics = set(result.scalars().all())

    available = [t for t in CURATED_TOPICS if t["topic"] not in recent_topics]
    if not available:
        available = CURATED_TOPICS

    return random.choice(available)
