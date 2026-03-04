// Core domain types matching backend schemas

export interface Agent {
  id: string;
  name: string;
  elo_rating: number;
  school_of_thought: string | null;
  model_info: Record<string, unknown>;
  current_position_snapshot: string | null;
  total_debates: number;
  is_active: boolean;
  created_at: string;
}

export interface Debate {
  id: string;
  topic: string;
  description: string | null;
  category: string | null;
  created_by: string;
  source_thesis_id: string | null;
  status: DebateStatus;
  config: Record<string, unknown>;
  phase_0_structure: Record<string, unknown> | null;
  max_rounds: number;
  current_round: number;
  convergence_signals: Record<string, unknown> | null;
  created_at: string;
  completed_at: string | null;
}

export type DebateStatus =
  | 'phase_0' | 'active' | 'converged' | 'completed'
  | 'deadlocked' | 'evaluation' | 'synthesis' | 'done'
  | 'evaluation_failed';

export interface Turn {
  id: string;
  debate_id: string;
  agent_id: string;
  round_number: number;
  turn_type: string;
  content: string;
  toulmin_tags: ToulminTag[];
  falsification_target: Record<string, unknown> | null;
  citation_references: CitationRef[];
  validation_status: 'pending' | 'valid' | 'rejected';
  validation_feedback: string | null;
  arbiter_quality_score: number | null;
  audience_avg_score: number | null;
  human_avg_score: number | null;
  agent_avg_score: number | null;
  created_at: string;
}

export interface ToulminTag {
  type: string;
  start: number;
  end: number;
  label: string;
}

export interface CitationRef {
  source: string;
  url?: string;
  excerpt?: string;
}

export interface Vote {
  vote_id: string;
  aggregate: number | null;
  count: number;
  human_avg: number | null;
  agent_avg: number | null;
  divergence_detected: boolean;
}

export interface Comment {
  id: string;
  debate_id: string;
  target_turn_id: string | null;
  author_type: string;
  author_id: string;
  parent_comment_id: string | null;
  content: string;
  upvote_count: number;
  created_at: string;
}

export interface Evaluation {
  evaluations: AgentEvaluation[];
  synthesis: SynthesisDoc | null;
}

export interface AgentEvaluation {
  agent_id: string;
  argument_quality: number;
  falsification_effectiveness: number;
  protective_belt_integrity: number;
  novel_contribution: number;
  structural_compliance: number;
  composite_score: number;
  elo_before: number;
  elo_after: number;
  narrative_feedback: string;
}

export interface SynthesisDoc {
  agreements: string;
  disagreements: string;
  novel_positions: string;
  open_questions: string;
}

export interface GraphNode {
  id: string;
  node_type: string;
  content: string;
  source_debate_id: string | null;
  quality_score: number | null;
  verification_status: string;
  metadata_: Record<string, unknown> | null;
}

export interface GraphEdge {
  id: string;
  edge_type: string;
  source_node_id: string;
  target_node_id: string;
  strength: number;
  source_debate_id: string | null;
}

export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface Thesis {
  id: string;
  agent_id: string;
  claim: string;
  school_of_thought: string | null;
  evidence_summary: string | null;
  challenge_type: string | null;
  category: string | null;
  is_gap_filling: boolean;
  gap_reference: string | null;
  status: string;
  view_count: number;
  challenger_count: number;
  created_at: string;
}

export interface ControlPlane {
  my_submission_status: 'pending' | 'submitted' | 'validated' | 'rejected';
  round_submissions: { total: number; submitted: number };
  turn_deadline_at: string | null;
  action_needed: 'submit_turn' | 'wait' | 'debate_complete' | 'resubmit';
}

export interface DebateStatusResponse extends Debate {
  control_plane: ControlPlane | null;
}

export type WSEvent =
  | { type: 'turn_submitted'; data: { turn_id: string; agent_id: string; round: number; turn_type: string } }
  | { type: 'turn_validated'; data: { turn_id: string; status: string; feedback?: string } }
  | { type: 'debate_completed'; data: { status: string } }
  | { type: 'vote_cast'; data: { vote_id: string; target_id: string; score: number; divergence_detected: boolean } }
  | { type: 'comment_posted'; data: { comment_id: string; author_type: string } }
  | { type: 'citation_challenge'; data: { challenge_id: string; target_turn_id: string } };
