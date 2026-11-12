# SecondSense

Application-layer **pre-checkout manipulation-risk and consent layer** for PayPal *merchant checkout* (Orders v2, `intent=CAPTURE`). Prototype for PayPal **Sandbox** only. Not a PayPal product, not escrow, not P2P protection. Risk scores are heuristics, not calibrated probabilities.

## What the backend enforces (FastAPI, `backend/`)
- Risk is computed **server-side** from text you submit; the raw text is never stored or logged (only signal categories + scores).
- Price/currency come from a **server catalog** (`coffee`, `plumber`, `relief_donation`, `safety_transfer`); clients send only an item id.
- **High-risk gate:** order creation and capture are refused until the session has a recorded acknowledgment bound to the exact warning digest, made after a server-measured pause (default 20 s). A trusted-contact "suspected scam" verdict can only raise friction.
- **PayPal Orders v2:** create order (idempotent `PayPal-Request-Id`), re-read the order before capture and verify id, intent, status, single purchase unit, `custom_id` = session, amount, currency and (if `PAYPAL_MERCHANT_ID` is set) payee; capture once; unknown outcomes need reconciliation rather than a blind retry.
- Hash-chained audit events per session; owner-key scoping; rate limiting; explicit CORS origins.

## Run
```bash
# backend
cd backend && python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # add PayPal SANDBOX client id/secret
uvicorn main:app --port 8000
python -m pytest            # mocked PayPal transport; no network

# frontend
cd frontend && npm install && cp .env.example .env.local
npm run dev                 # http://localhost:3000  (build: npm run build)
```
`ALLOWED_ORIGINS` in `backend/.env` must include the frontend origin (default `http://localhost:3000`). The PayPal client ID is served to the browser by `GET /api/config`; the secret never leaves the backend.

## Demo scenarios (Workspace page)
| Scenario | Observed result (run against the live backend) |
|---|---|
| Routine coffee ($35) | low, score 0, no friction |
| Emergency plumber ($450) | low, score 0, legitimate urgency, no friction |
| Wildfire relief request ($200) | high, score 63, checkout locked until acknowledged |
| Impersonated fraud team ($1200) | high, score 100, checkout locked until acknowledged |

## Verification status
- Backend: `pytest` = 85 passed (risk engine, gate, API flow, PayPal gateway via `httpx.MockTransport`).
- Frontend: `tsc --noEmit` clean and `next build` succeeds.
- **PENDING: live PayPal Sandbox run.** Not performed: no Sandbox credentials were available. Order create/get/capture are implemented and tested only against a mocked transport. With no credentials the API returns `503 paypal_not_configured`; no real order or capture id has been produced.
- Not built: end-user auth (owner key is not an identity), calibration, merchant/charity verification, OCR/LLM explanations, retention policy, shared rate limiting, CSP.
