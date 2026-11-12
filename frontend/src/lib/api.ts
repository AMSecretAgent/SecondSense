export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type RiskLevel = 'low' | 'review' | 'high';
export type Verdict = 'safe_to_proceed' | 'suspected_scam';

export interface Signal { label: string; detected: boolean; points: number }
export interface Warning { version: string; title: string; points: string[]; digest: string; min_pause_seconds: number; pause_remaining_seconds: number }
export interface Gate { allowed: boolean; code: string; message: string; ack_required: boolean; pause_remaining_seconds: number }
export interface ReviewInfo { id: string; created_at: string; expires_at: string; revoked: boolean; expired: boolean; verdict: Verdict | null; verdict_at: string | null }

export interface SessionView {
  session_id: string;
  status: string;
  created_at: string;
  expires_at: string;
  checkout: { item_id: string; label: string; amount: string; currency: string; merchant: { id: string; name: string; verified: boolean; note: string } };
  risk: { score: number; level: RiskLevel; effective_level: RiskLevel; signals: Record<string, Signal>; explanation: string; limitations: string; engine_version: string; scores_are_heuristic: boolean };
  gate: Gate;
  warning: Warning | null;
  reviews: ReviewInfo[];
  order_id: string | null;
  capture_id: string | null;
  analysis?: { evidence: Record<string, string[]> };
}

export interface AppConfig {
  merchant: { id: string; name: string; verified: boolean; note: string };
  items: { id: string; label: string; amount: string; currency: string }[];
  payments: { configured: boolean; environment: 'sandbox' | 'live'; client_id: string | null; currency: string; flow: string };
  risk_engine: { version: string; heuristic: boolean; calibrated: boolean };
  high_risk_min_pause_seconds: number;
}

export interface LedgerRow {
  session_id: string; created_at: string; status: string; risk_score: number; risk_level: RiskLevel; effective_level: RiskLevel;
  signals: { key: string; label: string }[]; item_label: string; amount: string; currency: string; acknowledged: boolean; capture_id: string | null;
}

export interface CaptureResult { status: string; capture_id: string; amount: string; currency: string; environment: string; already_captured: boolean; note: string }
export interface ReviewCreated { review_id: string; review_path: string; expires_at: string; shares: string[]; note: string }
export interface PublicReview {
  verdict: Verdict | null; expires_at: string;
  payment: { amount: string; currency: string; merchant_label: string; merchant_verified: boolean };
  analysis: { risk_score: number; risk_level: RiskLevel; signals: Record<string, { label: string; detected: boolean }>; explanation: string; limitations: string };
  note: string;
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public extra: Record<string, unknown> = {}) {
    super(message);
  }
}

const KEY_RE = /^[A-Za-z0-9_-]{32,128}$/;
let memoryKey: string | null = null;

function newKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** Random per-browser key that scopes sessions to this browser. It is NOT user authentication. */
export function ownerKey(): string {
  try {
    const stored = window.localStorage.getItem('ss_owner_key');
    if (stored && KEY_RE.test(stored)) return stored;
    const created = newKey();
    window.localStorage.setItem('ss_owner_key', created);
    return created;
  } catch {
    return (memoryKey ??= newKey());
  }
}

export async function api<T>(path: string, opts: { body?: unknown; owner?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
  if (opts.owner !== false) headers['X-Owner-Key'] = ownerKey();
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method: opts.body !== undefined ? 'POST' : 'GET', headers, body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined, cache: 'no-store' });
  } catch {
    throw new ApiError(0, 'network', `Cannot reach the SecondSense API at ${API_URL}. Is the backend running and is this origin in ALLOWED_ORIGINS?`);
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const e = data?.error ?? {};
    throw new ApiError(res.status, e.code ?? 'http_error', e.message ?? `Request failed (${res.status})`, e);
  }
  return data as T;
}

export const errorText = (e: unknown): string => (e instanceof ApiError ? e.message : e instanceof Error ? e.message : 'Something went wrong.');

export const endpoints = {
  config: () => api<AppConfig>('/api/config', { owner: false }),
  analyze: (context: string, checkout_item_id: string) => api<SessionView>('/api/analyze', { body: { context, checkout_item_id } }),
  session: (id: string) => api<SessionView>(`/api/sessions/${encodeURIComponent(id)}`),
  sessions: () => api<LedgerRow[]>('/api/sessions'),
  acknowledge: (id: string, warning_digest: string) => api<SessionView>(`/api/sessions/${encodeURIComponent(id)}/acknowledge`, { body: { warning_digest, confirm: true } }),
  createReview: (session_id: string) => api<ReviewCreated>('/api/reviews', { body: { session_id, consent: true } }),
  revokeReview: (id: string) => api<{ revoked: boolean }>(`/api/reviews/${encodeURIComponent(id)}/revoke`, { body: {} }),
  createOrder: (session_id: string) => api<{ id: string; reused: boolean }>('/api/paypal/orders', { body: { session_id } }),
  capture: (session_id: string, orderId: string) => api<CaptureResult>(`/api/paypal/orders/${encodeURIComponent(orderId)}/capture`, { body: { session_id } }),
  publicReview: (token: string) => api<PublicReview>(`/api/reviews/${encodeURIComponent(token)}`, { owner: false }),
  submitVerdict: (token: string, verdict: Verdict) => api<{ verdict: Verdict; note: string }>(`/api/reviews/${encodeURIComponent(token)}/verdict`, { body: { verdict }, owner: false }),
};
