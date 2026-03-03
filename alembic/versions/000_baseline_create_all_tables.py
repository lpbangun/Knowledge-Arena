"""Baseline: create all tables

Revision ID: 000_baseline
Revises: None
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "000_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- ENUM TYPES ---
    # Create all PostgreSQL enum types used by the models
    debate_status = postgresql.ENUM(
        "phase_0", "active", "converged", "completed", "deadlocked",
        "evaluation", "synthesis", "done", "evaluation_failed",
        name="debatetatus",
        create_type=False,
    )
    debate_status_enum = postgresql.ENUM(
        "phase_0", "active", "converged", "completed", "deadlocked",
        "evaluation", "synthesis", "done", "evaluation_failed",
        name="debatetatus",
    )
    debate_status_enum.create(op.get_bind(), checkfirst=True)

    participant_role_enum = postgresql.ENUM(
        "debater", "audience",
        name="participantrole",
    )
    participant_role_enum.create(op.get_bind(), checkfirst=True)

    turn_validation_status_enum = postgresql.ENUM(
        "pending", "valid", "rejected", "resubmitted",
        name="turnvalidationstatus",
    )
    turn_validation_status_enum.create(op.get_bind(), checkfirst=True)

    citation_challenge_status_enum = postgresql.ENUM(
        "pending", "verified", "failed", "frivolous",
        name="citationchallengestatus",
    )
    citation_challenge_status_enum.create(op.get_bind(), checkfirst=True)

    thesis_status_enum = postgresql.ENUM(
        "open", "challenged", "debating", "resolved", "standing_unchallenged",
        name="thesisstatus",
    )
    thesis_status_enum.create(op.get_bind(), checkfirst=True)

    vote_type_enum = postgresql.ENUM(
        "turn_quality", "debate_outcome",
        name="votetype",
    )
    vote_type_enum.create(op.get_bind(), checkfirst=True)

    voter_type_enum = postgresql.ENUM(
        "human", "agent",
        name="votertype",
    )
    voter_type_enum.create(op.get_bind(), checkfirst=True)

    snapshot_type_enum = postgresql.ENUM(
        "pre_debate", "post_debate",
        name="snapshottype",
    )
    snapshot_type_enum.create(op.get_bind(), checkfirst=True)

    graph_node_type_enum = postgresql.ENUM(
        "hard_core", "auxiliary_hypothesis", "empirical_claim", "evidence",
        "synthesis_position", "open_question", "standing_thesis",
        name="graphnodetype",
    )
    graph_node_type_enum.create(op.get_bind(), checkfirst=True)

    graph_edge_type_enum = postgresql.ENUM(
        "supports", "contradicts", "falsifies", "qualifies", "extends",
        "synthesizes", "challenges", "evolved_from",
        name="graphedgetype",
    )
    graph_edge_type_enum.create(op.get_bind(), checkfirst=True)

    verification_status_enum = postgresql.ENUM(
        "verified", "unverified", "challenged", "falsified",
        name="verificationstatus",
    )
    verification_status_enum.create(op.get_bind(), checkfirst=True)

    user_role_enum = postgresql.ENUM(
        "observer", "admin",
        name="userrole",
    )
    user_role_enum.create(op.get_bind(), checkfirst=True)

    # --- TABLES ---

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=True),
        sa.Column("auth_provider", sa.String(50), nullable=False, server_default="email"),
        sa.Column("role", sa.Enum("observer", "admin", name="userrole"), nullable=False, server_default="observer"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # agents
    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("model_info", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("school_of_thought", sa.String(200), nullable=True),
        sa.Column("elo_rating", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("elo_history", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("total_debates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("api_key_hash", sa.String(256), nullable=False),
        sa.Column("api_key_prefix", sa.String(8), nullable=False),
        sa.Column("current_position_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agents_name", "agents", ["name"], unique=True)
    op.create_index("ix_agents_api_key_prefix", "agents", ["api_key_prefix"])
    op.create_unique_constraint("uq_agents_api_key_hash", "agents", ["api_key_hash"])

    # graph_nodes (must exist before theses due to FK from theses.gap_reference)
    op.create_table(
        "graph_nodes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("node_type", sa.Enum(
            "hard_core", "auxiliary_hypothesis", "empirical_claim", "evidence",
            "synthesis_position", "open_question", "standing_thesis",
            name="graphnodetype",
        ), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_debate_id", sa.Uuid(), nullable=True),
        sa.Column("source_agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("source_turn_id", sa.Uuid(), nullable=True),
        sa.Column("toulmin_category", sa.String(20), nullable=True),
        sa.Column("verification_status", sa.Enum(
            "verified", "unverified", "challenged", "falsified",
            name="verificationstatus",
        ), nullable=False, server_default="unverified"),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("challenge_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_graph_nodes_node_type", "graph_nodes", ["node_type"])

    # theses (depends on agents, graph_nodes)
    op.create_table(
        "theses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("school_of_thought", sa.String(200), nullable=True),
        sa.Column("evidence_summary", sa.Text(), nullable=True),
        sa.Column("challenge_type", sa.String(100), nullable=True),
        sa.Column("toulmin_tags", postgresql.JSONB(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("is_gap_filling", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("gap_reference", sa.Uuid(), sa.ForeignKey("graph_nodes.id"), nullable=True),
        sa.Column("status", sa.Enum(
            "open", "challenged", "debating", "resolved", "standing_unchallenged",
            name="thesisstatus",
        ), nullable=False, server_default="open"),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("challenger_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_theses_agent_id", "theses", ["agent_id"])
    op.create_index("ix_theses_category", "theses", ["category"])

    # debates (depends on agents, theses)
    op.create_table(
        "debates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("source_thesis_id", sa.Uuid(), sa.ForeignKey("theses.id"), nullable=True),
        sa.Column("status", sa.Enum(
            "phase_0", "active", "converged", "completed", "deadlocked",
            "evaluation", "synthesis", "done", "evaluation_failed",
            name="debatetatus",
        ), nullable=False, server_default="phase_0"),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("phase_0_structure", postgresql.JSONB(), nullable=True),
        sa.Column("max_rounds", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("current_round", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("convergence_signals", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_debates_category", "debates", ["category"])

    # turns (depends on debates, agents)
    op.create_table(
        "turns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("debate_id", sa.Uuid(), sa.ForeignKey("debates.id"), nullable=False),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("turn_type", sa.String(20), nullable=False, server_default="argument"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("toulmin_tags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("falsification_target", postgresql.JSONB(), nullable=True),
        sa.Column("citation_references", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("validation_status", sa.Enum(
            "pending", "valid", "rejected", "resubmitted",
            name="turnvalidationstatus",
        ), nullable=False, server_default="pending"),
        sa.Column("validation_feedback", sa.Text(), nullable=True),
        sa.Column("arbiter_quality_score", sa.Float(), nullable=True),
        sa.Column("audience_avg_score", sa.Float(), nullable=True),
        sa.Column("human_avg_score", sa.Float(), nullable=True),
        sa.Column("agent_avg_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_turns_debate_id", "turns", ["debate_id"])
    op.create_index("ix_turns_agent_id", "turns", ["agent_id"])

    # debate_participants (depends on debates, agents)
    op.create_table(
        "debate_participants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("debate_id", sa.Uuid(), sa.ForeignKey("debates.id"), nullable=False),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("role", sa.Enum("debater", "audience", name="participantrole"), nullable=False),
        sa.Column("school_of_thought", sa.String(200), nullable=True),
        sa.Column("hard_core", sa.Text(), nullable=True),
        sa.Column("auxiliary_hypotheses", postgresql.JSONB(), nullable=True),
        sa.Column("citation_challenges_remaining", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("joined_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("debate_id", "agent_id", name="uq_debate_participants_debate_agent"),
    )
    op.create_index("ix_debate_participants_debate_id", "debate_participants", ["debate_id"])
    op.create_index("ix_debate_participants_agent_id", "debate_participants", ["agent_id"])

    # citation_challenges (depends on debates, turns)
    op.create_table(
        "citation_challenges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("debate_id", sa.Uuid(), sa.ForeignKey("debates.id"), nullable=False),
        sa.Column("challenger_id", sa.Uuid(), nullable=False),
        sa.Column("challenger_type", sa.Enum("human", "agent", name="votertype"), nullable=False),
        sa.Column("target_turn_id", sa.Uuid(), sa.ForeignKey("turns.id"), nullable=False),
        sa.Column("target_citation_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum(
            "pending", "verified", "failed", "frivolous",
            name="citationchallengestatus",
        ), nullable=False, server_default="pending"),
        sa.Column("response_evidence", postgresql.JSONB(), nullable=True),
        sa.Column("arbiter_ruling", sa.Text(), nullable=True),
        sa.Column("elo_impact", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_citation_challenges_debate_id", "citation_challenges", ["debate_id"])

    # votes
    op.create_table(
        "votes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("vote_type", sa.Enum("turn_quality", "debate_outcome", name="votetype"), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("voter_type", sa.Enum("human", "agent", name="votertype"), nullable=False),
        sa.Column("voter_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("outcome_choice", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("target_id", "voter_id", "vote_type", name="uq_votes_target_voter_type"),
    )
    op.create_index("ix_votes_target_id", "votes", ["target_id"])

    # comments (depends on debates, turns)
    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("debate_id", sa.Uuid(), sa.ForeignKey("debates.id"), nullable=False),
        sa.Column("target_turn_id", sa.Uuid(), sa.ForeignKey("turns.id"), nullable=True),
        sa.Column("author_type", sa.Enum("human", "agent", name="votertype"), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("parent_comment_id", sa.Uuid(), sa.ForeignKey("comments.id"), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("upvote_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_comments_debate_id", "comments", ["debate_id"])

    # amicus_briefs (depends on debates, agents)
    op.create_table(
        "amicus_briefs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("debate_id", sa.Uuid(), sa.ForeignKey("debates.id"), nullable=False),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("toulmin_tags", postgresql.JSONB(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_amicus_briefs_debate_id", "amicus_briefs", ["debate_id"])

    # graph_edges (depends on graph_nodes, debates, agents)
    # Add deferred FK for graph_nodes.source_debate_id and source_turn_id now that debates/turns exist
    op.create_table(
        "graph_edges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_node_id", sa.Uuid(), sa.ForeignKey("graph_nodes.id"), nullable=False),
        sa.Column("target_node_id", sa.Uuid(), sa.ForeignKey("graph_nodes.id"), nullable=False),
        sa.Column("edge_type", sa.Enum(
            "supports", "contradicts", "falsifies", "qualifies", "extends",
            "synthesizes", "challenges", "evolved_from",
            name="graphedgetype",
        ), nullable=False),
        sa.Column("source_debate_id", sa.Uuid(), sa.ForeignKey("debates.id"), nullable=True),
        sa.Column("source_agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("strength", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_graph_edges_source_node_id", "graph_edges", ["source_node_id"])
    op.create_index("ix_graph_edges_target_node_id", "graph_edges", ["target_node_id"])

    # Add deferred FKs on graph_nodes for source_debate_id and source_turn_id
    op.create_foreign_key(
        "fk_graph_nodes_source_debate_id",
        "graph_nodes", "debates",
        ["source_debate_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_graph_nodes_source_turn_id",
        "graph_nodes", "turns",
        ["source_turn_id"], ["id"],
    )

    # debate_evaluations (depends on debates, agents)
    op.create_table(
        "debate_evaluations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("debate_id", sa.Uuid(), sa.ForeignKey("debates.id"), nullable=False),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("argument_quality", sa.Float(), nullable=False),
        sa.Column("falsification_effectiveness", sa.Float(), nullable=False),
        sa.Column("protective_belt_integrity", sa.Float(), nullable=False),
        sa.Column("novel_contribution", sa.Float(), nullable=False),
        sa.Column("structural_compliance", sa.Float(), nullable=False),
        sa.Column("composite_score", sa.Float(), nullable=False),
        sa.Column("elo_before", sa.Integer(), nullable=False),
        sa.Column("elo_after", sa.Integer(), nullable=False),
        sa.Column("narrative_feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_debate_evaluations_debate_id", "debate_evaluations", ["debate_id"])

    # synthesis_documents (depends on debates)
    op.create_table(
        "synthesis_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("debate_id", sa.Uuid(), sa.ForeignKey("debates.id"), nullable=False),
        sa.Column("agreements", sa.Text(), nullable=False),
        sa.Column("disagreements", sa.Text(), nullable=False),
        sa.Column("novel_positions", sa.Text(), nullable=False),
        sa.Column("open_questions", sa.Text(), nullable=False),
        sa.Column("graph_nodes_created", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("graph_edges_created", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("debate_id", name="uq_synthesis_documents_debate_id"),
    )

    # belief_update_packets (depends on debates, agents)
    op.create_table(
        "belief_update_packets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("debate_id", sa.Uuid(), sa.ForeignKey("debates.id"), nullable=False),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("concessions_made", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("concessions_resisted", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("new_evidence", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("strongest_counterarguments", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("synthesis_insights", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("recommended_updates", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("falsification_outcomes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_belief_update_packets_debate_id", "belief_update_packets", ["debate_id"])
    op.create_index("ix_belief_update_packets_agent_id", "belief_update_packets", ["agent_id"])

    # position_snapshots (depends on agents, debates, belief_update_packets)
    op.create_table(
        "position_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("debate_id", sa.Uuid(), sa.ForeignKey("debates.id"), nullable=True),
        sa.Column("bup_id", sa.Uuid(), sa.ForeignKey("belief_update_packets.id"), nullable=True),
        sa.Column("snapshot_type", sa.Enum("pre_debate", "post_debate", name="snapshottype"), nullable=False),
        sa.Column("hard_core", sa.Text(), nullable=False),
        sa.Column("auxiliary_hypotheses", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("qualifier_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence_references", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_position_snapshots_agent_id", "position_snapshots", ["agent_id"])


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("position_snapshots")
    op.drop_table("belief_update_packets")
    op.drop_table("synthesis_documents")
    op.drop_table("debate_evaluations")

    op.drop_constraint("fk_graph_nodes_source_turn_id", "graph_nodes", type_="foreignkey")
    op.drop_constraint("fk_graph_nodes_source_debate_id", "graph_nodes", type_="foreignkey")
    op.drop_table("graph_edges")

    op.drop_table("amicus_briefs")
    op.drop_table("comments")
    op.drop_table("votes")
    op.drop_table("citation_challenges")
    op.drop_table("debate_participants")
    op.drop_table("turns")
    op.drop_table("debates")
    op.drop_table("theses")
    op.drop_table("graph_nodes")
    op.drop_table("agents")
    op.drop_table("users")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS snapshottype")
    op.execute("DROP TYPE IF EXISTS graphedgetype")
    op.execute("DROP TYPE IF EXISTS graphnodetype")
    op.execute("DROP TYPE IF EXISTS verificationstatus")
    op.execute("DROP TYPE IF EXISTS votertype")
    op.execute("DROP TYPE IF EXISTS votetype")
    op.execute("DROP TYPE IF EXISTS thesisstatus")
    op.execute("DROP TYPE IF EXISTS citationchallengestatus")
    op.execute("DROP TYPE IF EXISTS turnvalidationstatus")
    op.execute("DROP TYPE IF EXISTS participantrole")
    op.execute("DROP TYPE IF EXISTS debatetatus")
    op.execute("DROP TYPE IF EXISTS userrole")
