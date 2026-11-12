export type Maturity = 'working' | 'simulated' | 'pending';
export interface StatusItem { name: string; detail: string }

export const STATUS: Record<Maturity, StatusItem[]> = {
  working: [
    { name: 'Server-authoritative risk assessment', detail: 'The backend scores the supplied text and stores the result. Clients cannot submit or alter the risk level.' },
    { name: 'High-risk acknowledgment transition', detail: 'A paused checkout unlocks only through a recorded acknowledgment bound to the session and the exact warning shown, after a server-measured pause.' },
    { name: 'Server-side price, currency and merchant', detail: 'Amount and currency come from a server catalog. Requests that try to set them are rejected.' },
    { name: 'Capture verification and single capture', detail: 'Before capture the backend re-reads the order and checks amount, currency, session binding, status and (if configured) payee. A session can be captured once.' },
    { name: 'Consent-based trusted-contact review', detail: 'Expiring, revocable, single-verdict links. Advisory only. A concerned verdict raises friction; a reassuring one never lowers it.' },
    { name: 'Privacy by construction', detail: 'The raw message is not stored, shared or logged. Only signal categories and scores are persisted.' },
    { name: 'Tamper-evident audit trail', detail: 'Hash-chained events for each session (tamper-evident, not tamper-proof).' },
  ],
  simulated: [
    { name: 'Scenario messages and catalog items', detail: 'The four example messages and their priced items are demo data. The demo merchant is not a real or verified merchant.' },
    { name: 'Landing-page tier illustration', detail: 'Static illustration of the three friction levels. It is not live data.' },
  ],
  pending: [
    { name: 'Live PayPal Sandbox run', detail: 'Order create / get / capture calls are implemented and tested against a mocked HTTP transport. An end-to-end run needs your Sandbox credentials.' },
    { name: 'End-user authentication', detail: 'Sessions are scoped by a per-browser random key, which is not a user identity. Do not deploy publicly without real auth.' },
    { name: 'Calibration', detail: 'Scores are heuristics. No labelled evaluation set exists, so no error rates are claimed.' },
    { name: 'Merchant or charity verification', detail: 'Deliberately not inferred from names or invoices. Needs an authoritative registry.' },
    { name: 'Screenshot OCR, LLM explanations, retention and deletion policy, shared rate limiting, CSP', detail: 'Not built in this phase.' },
  ],
};
