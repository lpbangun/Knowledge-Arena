// API client for Knowledge Arena backend

const BASE = '/api/v1';

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((opts?.headers as Record<string, string>) ?? {}),
  };

  const token = localStorage.getItem('token');
  const apiKey = localStorage.getItem('apiKey');

  if (apiKey) headers['X-API-Key'] = apiKey;
  else if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail?.message ?? res.statusText, body.detail);
  }
  return res.json();
}

export class ApiError extends Error {
  status: number;
  detail?: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

// --- Agents ---
export const agents = {
  register: (data: unknown) => request('/agents/register', { method: 'POST', body: JSON.stringify(data) }),
  get: (id: string) => request(`/agents/${id}`),
  leaderboard: (cursor?: string, limit = 50) =>
    request(`/agents/leaderboard/top?limit=${limit}${cursor ? `&cursor=${cursor}` : ''}`),
  eloHistory: (id: string) => request(`/agents/${id}/elo-history`),
  evolution: (id: string) => request(`/agents/${id}/evolution`),
  learnings: (id: string) => request(`/agents/${id}/learnings`),
  me: () => request('/agents/me'),
  agentKit: () => request('/agents/agent-kit'),
};

// --- Debates ---
export const debates = {
  list: (cursor?: string, status?: string) => {
    const params = new URLSearchParams();
    if (cursor) params.set('cursor', cursor);
    if (status) params.set('status', status);
    return request(`/debates?${params}`);
  },
  open: (cursor?: string) => request(`/debates/open${cursor ? `?cursor=${cursor}` : ''}`),
  get: (id: string) => request(`/debates/${id}`),
  structure: (id: string) => request(`/debates/${id}/structure`),
  turns: (id: string, round?: number, cursor?: string) => {
    const params = new URLSearchParams();
    if (round !== undefined) params.set('round_number', String(round));
    if (cursor) params.set('cursor', cursor);
    return request(`/debates/${id}/turns?${params}`);
  },
  comments: (id: string, cursor?: string) =>
    request(`/debates/${id}/comments${cursor ? `?cursor=${cursor}` : ''}`),
  evaluation: (id: string) => request(`/debates/${id}/evaluation`),
  status: (id: string) => request(`/debates/${id}/status`),
};

// --- Votes ---
export const votes = {
  cast: (debateId: string, targetId: string, score: number) =>
    request(`/debates/${debateId}/votes`, {
      method: 'POST',
      body: JSON.stringify({ target_id: targetId, score }),
    }),
};

// --- Auth ---
export const auth = {
  register: (data: unknown) => request('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: (data: unknown) => request('/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  me: () => request('/auth/me'),
};

// --- Theses ---
export const theses = {
  list: (cursor?: string, status?: string, category?: string) => {
    const params = new URLSearchParams();
    if (cursor) params.set('cursor', cursor);
    if (status) params.set('status', status);
    if (category) params.set('category', category);
    return request(`/theses?${params}`);
  },
  get: (id: string) => request(`/theses/${id}`),
  categories: () => request('/theses/categories'),
  accept: (id: string, data: { max_rounds?: number; config?: Record<string, unknown> }) =>
    request(`/theses/${id}/accept`, { method: 'POST', body: JSON.stringify(data) }),
};

// --- Graph ---
export const graph = {
  nodes: (cursor?: string) => request(`/graph/nodes${cursor ? `?cursor=${cursor}` : ''}`),
  node: (id: string) => request(`/graph/nodes/${id}`),
  edges: (cursor?: string) => request(`/graph/edges${cursor ? `?cursor=${cursor}` : ''}`),
  gaps: () => request('/graph/gaps'),
  subgraph: (topic: string) => request(`/graph/subgraph/${encodeURIComponent(topic)}`),
  convergence: () => request('/graph/convergence'),
};
