import enum


class DebateStatus(str, enum.Enum):
    PHASE_0 = "phase_0"
    ACTIVE = "active"
    CONVERGED = "converged"
    COMPLETED = "completed"
    DEADLOCKED = "deadlocked"
    EVALUATION = "evaluation"
    SYNTHESIS = "synthesis"
    DONE = "done"
    EVALUATION_FAILED = "evaluation_failed"


class ParticipantRole(str, enum.Enum):
    DEBATER = "debater"
    AUDIENCE = "audience"


class TurnValidationStatus(str, enum.Enum):
    PENDING = "pending"
    VALID = "valid"
    REJECTED = "rejected"
    RESUBMITTED = "resubmitted"


class ToulminCategory(str, enum.Enum):
    CLAIM = "claim"
    DATA = "data"
    WARRANT = "warrant"
    BACKING = "backing"
    QUALIFIER = "qualifier"
    REBUTTAL = "rebuttal"


class CitationChallengeStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    FRIVOLOUS = "frivolous"


class ThesisStatus(str, enum.Enum):
    OPEN = "open"
    CHALLENGED = "challenged"
    DEBATING = "debating"
    RESOLVED = "resolved"
    STANDING_UNCHALLENGED = "standing_unchallenged"


class VoteType(str, enum.Enum):
    TURN_QUALITY = "turn_quality"
    DEBATE_OUTCOME = "debate_outcome"


class VoterType(str, enum.Enum):
    HUMAN = "human"
    AGENT = "agent"


class SnapshotType(str, enum.Enum):
    PRE_DEBATE = "pre_debate"
    POST_DEBATE = "post_debate"


class GraphNodeType(str, enum.Enum):
    HARD_CORE = "hard_core"
    AUXILIARY_HYPOTHESIS = "auxiliary_hypothesis"
    EMPIRICAL_CLAIM = "empirical_claim"
    EVIDENCE = "evidence"
    SYNTHESIS_POSITION = "synthesis_position"
    OPEN_QUESTION = "open_question"
    STANDING_THESIS = "standing_thesis"


class GraphEdgeType(str, enum.Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    FALSIFIES = "falsifies"
    QUALIFIES = "qualifies"
    EXTENDS = "extends"
    SYNTHESIZES = "synthesizes"
    CHALLENGES = "challenges"
    EVOLVED_FROM = "evolved_from"


class VerificationStatus(str, enum.Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    CHALLENGED = "challenged"
    FALSIFIED = "falsified"


class UserRole(str, enum.Enum):
    OBSERVER = "observer"
    ADMIN = "admin"


class DebateFormat(str, enum.Enum):
    LAKATOS = "lakatos"
    OPEN = "open"
