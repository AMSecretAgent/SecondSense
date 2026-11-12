
"""FastAPI application factory. All risk, price and state decisions are made here, never by the client."""
from __future__ import annotations

import json
import logging
import re
from datetime import timedelta
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__, audit, catalog, checkout_gate as gate, clock, db, risk_engine, store, views
from .config import Settings
from .errors import ApiError
from .order_verification import ExpectedPayment, OrderMismatch, extract_capture, verify_order
from .paypal_gateway import PayPalError, PayPalGateway, PaymentGateway
from .schemas import AcknowledgeIn, AnalyzeIn, CaptureIn, OrderIn, ReviewCreateIn, VerdictIn
from .security import RateLimiter, hash_token, new_token, owner_hash_from_header

log = logging.getLogger("secondsense")
ORDER_ID_RE = re.compile(r"^[A-Z0-9]{10,30}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,128}$")
REVIEW_SHARES = ["risk level and score", "which signal categories were detected", "payment amount, currency and merchant label"]


def _gate_error(d: gate.GateDecision) -> ApiError:
    status = {
        gate.SESSION_EXPIRED: 410,
        gate.ACK_REQUIRED: 403,
        gate.ACK_EXPIRED: 403,
        gate.ACK_STALE: 403,
    }.get(d.code, 409)
    return ApiError(
        status, d.code, d.message,
        ack_required=d.ack_required,
        pause_remaining_seconds=d.pause_remaining_seconds
    )


def _paypal_error(e: PayPalError) -> ApiError:
    extra = {
        k: v for k, v in (
            ("paypal_issue", e.issue),
            ("paypal_debug_id", e.debug_id)
        ) if v
    }
    return ApiError(e.http_status, e.code, e.message, **extra)


# Browser request model must be defined outside create_app.
class BrowserAnalyzeIn(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    context: str = Field(min_length=5, max_length=5000)


def create_app(
    settings: Settings | None = None,
    gateway: PaymentGateway | None = None
) -> FastAPI:
    settings = settings or Settings.from_env()
    db.init_db(settings.database_path)
    gw: PaymentGateway = gateway or PayPalGateway(settings)
    limiter = RateLimiter(settings.rate_limit_per_minute)
    cfg = gate.GateConfig(
        settings.high_risk_min_pause_seconds,
        settings.ack_valid_seconds
    )
    path = settings.database_path
    prod = settings.app_env == "production"





    app = FastAPI(
        title="SecondSense API",
        version=__version__,
        description=(
            "Application-layer pre-checkout manipulation-risk and consent layer "
            "for merchant checkout. Scores are heuristics, not calibrated "
            "probabilities. Not a PayPal product; not P2P protection."
        ),
        docs_url=None if prod else "/docs",
        redoc_url=None,
        openapi_url=None if prod else "/openapi.json",
    )
    app.state.settings = settings
    @app.get("/api/reputation/youtube")
    def youtube_reputation(seller: str):
        import os
        import requests
        from fastapi import HTTPException

        seller = seller.strip()

        if len(seller) < 2 or len(seller) > 100:
            raise HTTPException(
                status_code=400,
                detail="Enter a valid seller name"
            )

        api_key = os.getenv("YOUTUBE_API_KEY")

        if not api_key:
            raise HTTPException(
                status_code=503,
                detail="YouTube API key not configured"
            )

        query = f'"{seller}" review scam delivery refund'

        try:
            response = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "maxResults": 10,
                    "key": api_key
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:
            raise HTTPException(
                status_code=502,
                detail="YouTube search unavailable"
            )

        videos = []

        for item in data.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})

            if not video_id:
                continue

            videos.append({
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt"),
                "description": snippet.get("description", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}"
            })

        return {
            "seller": seller,
            "status": "search_results_only",
            "videos": videos,
            "disclaimer": (
                "Search results are not verified customer experiences "
                "or evidence that a seller is fraudulent."
            )
        }

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Owner-Key"],
        max_age=600,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        headers = (
            {"Retry-After": str(exc.extra["retry_after_seconds"])}
            if "retry_after_seconds" in exc.extra else None
        )
        return JSONResponse(
            exc.body(),
            status_code=exc.status,
            headers=headers
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        fields = [
            {
                "field": ".".join(
                    str(p) for p in e["loc"] if p != "body"
                ),
                "problem": e["type"]
            }
            for e in exc.errors()
        ]
        return JSONResponse(
            {
                "error": {
                    "code": "validation_error",
                    "message": "Request was not valid.",
                    "fields": fields
                }
            },
            status_code=422
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return JSONResponse(
            {
                "error": {
                    "code": "http_error",
                    "message": str(exc.detail)
                }
            },
            status_code=exc.status_code
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.error("unhandled error type=%s", type(exc).__name__)
        return JSONResponse(
            {
                "error": {
                    "code": "internal_error",
                    "message": "Unexpected server error."
                }
            },
            status_code=500
        )

    def limit(request: Request, bucket: str) -> None:
        limiter.check(
            f"{bucket}:{request.client.host if request.client else 'unknown'}"
        )

    # ------------------------------------------------------------
    # Health and public configuration
    # ------------------------------------------------------------

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/config")
    def config() -> dict[str, Any]:
        return {
            "merchant": catalog.MERCHANT,
            "items": [
                {
                    "id": i.id,
                    "label": i.label,
                    "amount": i.amount_str,
                    "currency": i.currency
                }
                for i in catalog.CATALOG.values()
            ],
            "payments": {
                "configured": settings.paypal_configured,
                "environment": settings.paypal_environment,
                "client_id": (
                    settings.paypal_client_id
                    if settings.paypal_configured else None
                ),
                "currency": "USD",
                "flow": (
                    "merchant checkout (Orders v2, intent=CAPTURE); "
                    "not escrow, not P2P"
                )
            },
            "risk_engine": {
                "version": risk_engine.ENGINE_VERSION,
                "heuristic": True,
                "calibrated": False
            },
            "high_risk_min_pause_seconds":
                settings.high_risk_min_pause_seconds,
        }

    # ------------------------------------------------------------
    # Browser risk analysis (NEW)
    # ------------------------------------------------------------

    @app.post("/api/browser/analyze")
    def browser_analyze(
        body: BrowserAnalyzeIn,
        request: Request
    ):
        limit(request, "browser_analyze")

        result = risk_engine.analyze(body.context)

        return {
            "url": body.url,
            "risk_score": result["risk_score"],
            "risk_level": result["risk_level"],
            "signals": result["signals"],
            "explanation": result["explanation"],
            "limitations": result["limitations"],
            "engine_version": result["engine_version"]
        }

    # ------------------------------------------------------------
    # Analysis and sessions
    # ------------------------------------------------------------

    @app.post("/api/analyze")
    def analyze(
        body: AnalyzeIn,
        request: Request,
        x_owner_key: str | None = Header(default=None)
    ):
        limit(request, "analyze")
        owner = owner_hash_from_header(x_owner_key)

        item = catalog.CATALOG.get(body.checkout_item_id)
        if item is None:
            raise ApiError(
                422,
                "unknown_checkout_item",
                "Unknown checkout item."
            )

        result = risk_engine.analyze(body.context)
        now = clock.utcnow()
        sid = new_token(16)

        with db.transaction(path) as conn:
            conn.execute(
                "INSERT INTO sessions "
                "(id,owner_hash,item_id,item_label,amount_value,currency,"
                "risk_score,risk_level,signals_json,context_chars,status,"
                "created_at,expires_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    sid,
                    owner,
                    item.id,
                    item.label,
                    item.amount_str,
                    item.currency,
                    result["risk_score"],
                    result["risk_level"],
                    json.dumps(risk_engine.persistable_signals(result)),
                    len(body.context),
                    gate.ANALYZED,
                    clock.iso(now),
                    clock.iso(
                        now + timedelta(
                            seconds=settings.session_ttl_seconds
                        )
                    )
                )
            )

            audit.append(
                conn,
                sid,
                "session_created",
                {
                    "risk_level": result["risk_level"],
                    "risk_score": result["risk_score"],
                    "engine": risk_engine.ENGINE_VERSION,
                    "item_id": item.id,
                    "amount": item.amount_str,
                    "currency": item.currency
                }
            )

            view = views.session_view(
                conn,
                store.owned_session(conn, sid, owner),
                settings
            )

        log.info(
            "session_created id=%s level=%s",
            sid[:8],
            result["risk_level"]
        )

        view["analysis"] = {
            "evidence": {
                k: v["evidence"]
                for k, v in result["signals"].items()
            }
        }
        return view

    @app.get("/api/sessions")
    def list_sessions(
        x_owner_key: str | None = Header(default=None)
    ):
        owner = owner_hash_from_header(x_owner_key)

        with db.connect(path) as conn:
            rows = conn.execute(
                "SELECT * FROM sessions "
                "WHERE owner_hash=? "
                "ORDER BY created_at DESC LIMIT 100",
                (owner,)
            ).fetchall()

            return [
                views.ledger_row(
                    r,
                    store.contact_flag(conn, r["id"]) is not None
                )
                for r in rows
            ]

    @app.get("/api/sessions/{session_id}")
    def get_session(
        session_id: str,
        x_owner_key: str | None = Header(default=None)
    ):
        owner = owner_hash_from_header(x_owner_key)

        with db.connect(path) as conn:
            return views.session_view(
                conn,
                store.owned_session(conn, session_id, owner),
                settings
            )

    @app.get("/api/sessions/{session_id}/audit")
    def get_audit(
        session_id: str,
        x_owner_key: str | None = Header(default=None)
    ):
        owner = owner_hash_from_header(x_owner_key)

        with db.connect(path) as conn:
            store.owned_session(conn, session_id, owner)
            return {
                "chain_valid": audit.verify_chain(conn, session_id),
                "events": audit.events(conn, session_id)
            }

    @app.post("/api/sessions/{session_id}/acknowledge")
    def acknowledge(
        session_id: str,
        body: AcknowledgeIn,
        request: Request,
        x_owner_key: str | None = Header(default=None)
    ):
        limit(request, "ack")
        owner = owner_hash_from_header(x_owner_key)
        err: ApiError | None = None

        with db.transaction(path) as conn:
            row = store.owned_session(conn, session_id, owner)
            g = store.gate_input(
                row,
                store.contact_flag(conn, session_id)
            )
            now = clock.utcnow()

            d = gate.evaluate_acknowledgment(
                g,
                body.warning_digest,
                now,
                cfg
            )

            if not d.allowed:
                audit.append(
                    conn,
                    session_id,
                    "acknowledgment_rejected",
                    {"code": d.code}
                )

                if (
                    d.code == gate.ACK_REQUIRED
                    and d.pause_remaining_seconds > 0
                ):
                    err = ApiError(
                        409,
                        "pause_not_elapsed",
                        d.message,
                        pause_remaining_seconds=d.pause_remaining_seconds
                    )
                else:
                    err = _gate_error(d)
            else:
                conn.execute(
                    "UPDATE sessions SET ack_at=?, ack_digest=?, "
                    "ack_risk_score=? WHERE id=? AND status=?",
                    (
                        clock.iso(now),
                        body.warning_digest,
                        row["risk_score"],
                        session_id,
                        gate.ANALYZED
                    )
                )

                audit.append(
                    conn,
                    session_id,
                    "high_risk_acknowledged",
                    {
                        "warning_digest": body.warning_digest,
                        "warning_version":
                            catalog.HIGH_RISK_WARNING_VERSION,
                        "risk_score": row["risk_score"],
                        "effective_level": d.effective_level
                    }
                )

                view = views.session_view(
                    conn,
                    store.owned_session(conn, session_id, owner),
                    settings
                )

        if err:
            raise err
        return view

    # ------------------------------------------------------------
    # Trusted-contact review
    # ------------------------------------------------------------

    @app.post("/api/reviews")
    def create_review(
        body: ReviewCreateIn,
        request: Request,
        x_owner_key: str | None = Header(default=None)
    ):
        limit(request, "review_create")
        owner = owner_hash_from_header(x_owner_key)

        if not body.consent:
            raise ApiError(
                400,
                "consent_required",
                "Explicit consent to share the analysis summary is required."
            )

        err = None

        with db.transaction(path) as conn:
            store.owned_session(conn, body.session_id, owner)
            now = clock.utcnow()

            active = conn.execute(
                "SELECT COUNT(*) c FROM reviews "
                "WHERE session_id=? "
                "AND revoked_at IS NULL AND expires_at>?",
                (body.session_id, clock.iso(now))
            ).fetchone()["c"]

            if active >= settings.max_reviews_per_session:
                err = ApiError(
                    409,
                    "review_limit_reached",
                    "Too many active review links for this session. "
                    "Revoke one first."
                )
            else:
                token, rid = new_token(32), new_token(8)
                exp = now + timedelta(
                    seconds=settings.review_ttl_seconds
                )

                conn.execute(
                    "INSERT INTO reviews "
                    "(id,token_hash,session_id,consent_at,"
                    "created_at,expires_at) VALUES (?,?,?,?,?,?)",
                    (
                        rid,
                        hash_token(token),
                        body.session_id,
                        clock.iso(now),
                        clock.iso(now),
                        clock.iso(exp)
                    )
                )

                audit.append(
                    conn,
                    body.session_id,
                    "review_link_created",
                    {
                        "review_id": rid,
                        "expires_at": clock.iso(exp),
                        "shares": REVIEW_SHARES
                    }
                )

        if err:
            raise err

        return {
            "review_id": rid,
            "review_path": f"/review/{token}",
            "expires_at": clock.iso(exp),
            "shares": REVIEW_SHARES,
            "note": (
                "Share this link yourself with someone you trust. "
                "Nothing is sent automatically. It is an advisory opinion, "
                "not a PayPal approval, and your original message "
                "is never shared."
            )
        }

    @app.post("/api/reviews/{review_id}/revoke")
    def revoke_review(
        review_id: str,
        request: Request,
        x_owner_key: str | None = Header(default=None)
    ):
        limit(request, "review_revoke")
        owner = owner_hash_from_header(x_owner_key)

        with db.transaction(path) as conn:
            row = conn.execute(
                "SELECT r.session_id FROM reviews r "
                "JOIN sessions s ON s.id=r.session_id "
                "WHERE r.id=? AND s.owner_hash=?",
                (review_id, owner)
            ).fetchone()

            if not row:
                raise ApiError(
                    404,
                    "review_not_found",
                    "Review link not found."
                )

            conn.execute(
                "UPDATE reviews SET revoked_at=? "
                "WHERE id=? AND revoked_at IS NULL",
                (clock.iso(clock.utcnow()), review_id)
            )

            audit.append(
                conn,
                row["session_id"],
                "review_link_revoked",
                {"review_id": review_id}
            )

        return {"revoked": True}

    def _review_by_token(conn, token: str):
        if not TOKEN_RE.fullmatch(token):
            raise ApiError(
                404,
                "review_not_found",
                "Review link not found."
            )

        row = conn.execute(
            "SELECT r.*, s.risk_score, s.risk_level, "
            "s.signals_json, s.amount_value, s.currency "
            "FROM reviews r "
            "JOIN sessions s ON s.id=r.session_id "
            "WHERE r.token_hash=?",
            (hash_token(token),)
        ).fetchone()

        if not row:
            raise ApiError(
                404,
                "review_not_found",
                "Review link not found."
            )

        if (
            row["revoked_at"]
            or clock.parse(row["expires_at"]) <= clock.utcnow()
        ):
            raise ApiError(
                410,
                "review_unavailable",
                "This review link has expired or been revoked."
            )

        return row

    @app.get("/api/reviews/{token}")
    def get_review(token: str, request: Request):
        limit(request, "review_get")

        with db.connect(path) as conn:
            row = _review_by_token(conn, token)

        labels = {
            r.key: r.label
            for r in risk_engine.RULES
        }

        sig = {
            k: {
                "label": labels.get(k, k),
                "detected": v["detected"]
            }
            for k, v in json.loads(row["signals_json"]).items()
        }

        return {
            "verdict": row["verdict"],
            "expires_at": row["expires_at"],
            "payment": {
                "amount": row["amount_value"],
                "currency": row["currency"],
                "merchant_label": catalog.MERCHANT["name"],
                "merchant_verified": False
            },
            "analysis": {
                "risk_score": row["risk_score"],
                "risk_level": row["risk_level"],
                "signals": sig,
                "explanation": risk_engine.explanation_for(
                    row["risk_level"]
                ),
                "limitations": risk_engine.LIMITATIONS
            },
            "note": (
                "Advisory only. You cannot approve, release or block "
                "a PayPal payment. The original message is not shared."
            )
        }

    @app.post("/api/reviews/{token}/verdict")
    def submit_verdict(
        token: str,
        body: VerdictIn,
        request: Request
    ):
        limit(request, "review_verdict")

        with db.transaction(path) as conn:
            row = _review_by_token(conn, token)
            now = clock.iso(clock.utcnow())

            changed = conn.execute(
                "UPDATE reviews SET verdict=?, verdict_at=? "
                "WHERE token_hash=? AND verdict IS NULL",
                (
                    body.verdict,
                    now,
                    hash_token(token)
                )
            ).rowcount

            if changed:
                audit.append(
                    conn,
                    row["session_id"],
                    "review_verdict",
                    {
                        "review_id": row["id"],
                        "verdict": body.verdict
                    }
                )

        if not changed:
            raise ApiError(
                409,
                "verdict_already_submitted",
                "A verdict was already recorded for this link."
            )

        return {
            "verdict": body.verdict,
            "note": (
                "Recorded as an advisory opinion. "
                "It does not verify a recipient or authorize "
                "a PayPal payment."
            )
        }

    # ------------------------------------------------------------
    # PayPal merchant checkout
    # ------------------------------------------------------------

    @app.post("/api/paypal/orders")
    def create_order(
        body: OrderIn,
        request: Request,
        x_owner_key: str | None = Header(default=None)
    ):
        limit(request, "order")
        owner = owner_hash_from_header(x_owner_key)

        deny: gate.GateDecision | None = None
        reuse: str | None = None

        with db.transaction(path) as conn:
            row = store.owned_session(
                conn,
                body.session_id,
                owner
            )
            now = clock.utcnow()

            if (
                row["status"] == gate.ORDER_CREATED
                and row["order_id"]
                and now < clock.parse(row["expires_at"])
            ):
                reuse = row["order_id"]
            else:
                d = gate.evaluate_order_creation(
                    store.gate_input(
                        row,
                        store.contact_flag(conn, row["id"])
                    ),
                    now,
                    cfg
                )

                if not d.allowed:
                    audit.append(
                        conn,
                        row["id"],
                        "order_blocked",
                        {"code": d.code}
                    )
                    deny = d
                else:
                    conn.execute(
                        "UPDATE sessions SET status=? "
                        "WHERE id=? AND status=?",
                        (
                            gate.ORDER_CREATING,
                            row["id"],
                            gate.ANALYZED
                        )
                    )
                    audit.append(
                        conn,
                        row["id"],
                        "order_creating",
                        {
                            "amount": row["amount_value"],
                            "currency": row["currency"]
                        }
                    )

        if reuse:
            return {"id": reuse, "reused": True}

        if deny:
            raise _gate_error(deny)

        try:
            order = gw.create_order(
                amount=row["amount_value"],
                currency=row["currency"],
                reference_id=row["item_id"],
                custom_id=row["id"],
                description=row["item_label"],
                idempotency_key=f"ss-order-{row['id']}",
                payee_merchant_id=settings.paypal_merchant_id
            )

            order_id = str(order.get("id", ""))

            if not ORDER_ID_RE.fullmatch(order_id):
                raise PayPalError(
                    "paypal_bad_response",
                    "PayPal returned an unexpected order identifier."
                )

        except PayPalError as exc:
            with db.transaction(path) as conn:
                conn.execute(
                    "UPDATE sessions SET status=? "
                    "WHERE id=? AND status=?",
                    (
                        gate.ANALYZED,
                        row["id"],
                        gate.ORDER_CREATING
                    )
                )

                audit.append(
                    conn,
                    row["id"],
                    "order_create_failed",
                    {
                        "code": exc.code,
                        "paypal_status": exc.paypal_status,
                        "debug_id": exc.debug_id
                    }
                )

            raise _paypal_error(exc)

        now = clock.utcnow()

        with db.transaction(path) as conn:
            conn.execute(
                "UPDATE sessions SET status=?, order_id=?, "
                "order_created_at=?, expires_at=? "
                "WHERE id=? AND status=?",
                (
                    gate.ORDER_CREATED,
                    order_id,
                    clock.iso(now),
                    clock.iso(
                        now + timedelta(
                            seconds=settings.order_capture_window_seconds
                        )
                    ),
                    row["id"],
                    gate.ORDER_CREATING
                )
            )

            audit.append(
                conn,
                row["id"],
                "order_created",
                {"order_id": order_id}
            )

        return {"id": order_id, "reused": False}

    @app.post("/api/paypal/orders/{order_id}/capture")
    def capture(
        order_id: str,
        body: CaptureIn,
        request: Request,
        x_owner_key: str | None = Header(default=None)
    ):
        limit(request, "capture")
        owner = owner_hash_from_header(x_owner_key)

        if not ORDER_ID_RE.fullmatch(order_id):
            raise ApiError(
                422,
                "invalid_order_id",
                "Invalid order ID."
            )

        env = settings.paypal_environment

        def done(
            row_capture_id: str,
            amount: str,
            currency: str,
            already: bool
        ) -> dict[str, Any]:
            return {
                "status": "COMPLETED",
                "capture_id": row_capture_id,
                "amount": amount,
                "currency": currency,
                "environment": env,
                "already_captured": already,
                "note": (
                    "Capture id as returned by the PayPal API. "
                    "Merchant checkout (Orders v2 CAPTURE); "
                    "funds are not held in escrow."
                )
            }

        deny: ApiError | None = None

        with db.transaction(path) as conn:
            row = store.owned_session(
                conn,
                body.session_id,
                owner
            )

            if row["order_id"] != order_id:
                audit.append(
                    conn,
                    row["id"],
                    "capture_blocked",
                    {"code": "order_session_mismatch"}
                )
                deny = ApiError(
                    409,
                    "order_session_mismatch",
                    "This order does not belong to this session."
                )

            elif row["status"] == gate.CAPTURED:
                return done(
                    row["capture_id"],
                    row["amount_value"],
                    row["currency"],
                    True
                )

            else:
                d = gate.evaluate_capture(
                    store.gate_input(
                        row,
                        store.contact_flag(conn, row["id"])
                    ),
                    clock.utcnow(),
                    cfg
                )

                if not d.allowed:
                    audit.append(
                        conn,
                        row["id"],
                        "capture_blocked",
                        {"code": d.code}
                    )
                    deny = _gate_error(d)

        if deny:
            raise deny

        sid = row["id"]
        amount = row["amount_value"]
        currency = row["currency"]

        expected = ExpectedPayment(
            sid,
            order_id,
            amount,
            currency,
            settings.paypal_merchant_id
        )

        def block(
            code: str,
            message: str,
            status: int = 409
        ) -> ApiError:
            with db.transaction(path) as c:
                audit.append(
                    c,
                    sid,
                    "capture_blocked",
                    {"code": code}
                )
            return ApiError(status, code, message)

        try:
            order = gw.get_order(order_id)
        except PayPalError as exc:
            raise _paypal_error(exc)

        try:
            verify_order(
                order,
                expected,
                allowed_statuses={"APPROVED", "COMPLETED"}
            )
        except OrderMismatch as exc:
            raise block(exc.code, exc.message)

        summary = (
            extract_capture(order)
            if order.get("status") == "COMPLETED"
            else None
        )

        if summary is None:
            started = clock.utcnow()
            busy = False

            with db.transaction(path) as conn:
                cur = conn.execute(
                    "SELECT status, capture_started_at "
                    "FROM sessions WHERE id=?",
                    (sid,)
                ).fetchone()

                stale = (
                    cur["status"] == gate.CAPTURE_PENDING
                    and cur["capture_started_at"]
                    and started - clock.parse(
                        cur["capture_started_at"]
                    ) > timedelta(
                        seconds=settings.capture_retry_after_seconds
                    )
                )

                if cur["status"] == gate.ORDER_CREATED:
                    ok = conn.execute(
                        "UPDATE sessions SET status=?, "
                        "capture_started_at=? "
                        "WHERE id=? AND status=?",
                        (
                            gate.CAPTURE_PENDING,
                            clock.iso(started),
                            sid,
                            gate.ORDER_CREATED
                        )
                    ).rowcount

                elif stale:
                    ok = conn.execute(
                        "UPDATE sessions SET capture_started_at=? "
                        "WHERE id=? AND status=? "
                        "AND capture_started_at=?",
                        (
                            clock.iso(started),
                            sid,
                            gate.CAPTURE_PENDING,
                            cur["capture_started_at"]
                        )
                    ).rowcount

                else:
                    ok = 0

                if ok:
                    audit.append(
                        conn,
                        sid,
                        "capture_started",
                        {"order_id": order_id}
                    )
                else:
                    busy = True

            if busy:
                raise ApiError(
                    409,
                    "capture_in_progress",
                    "A capture is already in progress "
                    "or finished for this session."
                )

            try:
                result = gw.capture_order(
                    order_id,
                    idempotency_key=f"ss-capture-{sid}-{order_id}"
                )

            except PayPalError as exc:
                definitive = (
                    exc.paypal_status is not None
                    and 400 <= exc.paypal_status < 500
                )

                with db.transaction(path) as conn:
                    if definitive:
                        conn.execute(
                            "UPDATE sessions SET status=? "
                            "WHERE id=? AND status=?",
                            (
                                gate.ORDER_CREATED,
                                sid,
                                gate.CAPTURE_PENDING
                            )
                        )

                    audit.append(
                        conn,
                        sid,
                        "capture_failed",
                        {
                            "code": exc.code,
                            "paypal_status": exc.paypal_status,
                            "issue": exc.issue,
                            "debug_id": exc.debug_id,
                            "state_unknown": not definitive
                        }
                    )

                err = _paypal_error(exc)

                if not definitive:
                    err.extra["state_unknown"] = True

                raise err

            summary = extract_capture(result)

        expected_amount = str(
            Decimal(amount).quantize(Decimal("0.01"))
        )

        ok_capture = (
            summary is not None
            and summary.status == "COMPLETED"
            and (summary.amount, summary.currency)
            == (expected_amount, currency)
        )

        with db.transaction(path) as conn:
            if ok_capture:
                conn.execute(
                    "UPDATE sessions SET status=?, capture_id=?, "
                    "captured_at=? WHERE id=? "
                    "AND status IN (?,?)",
                    (
                        gate.CAPTURED,
                        summary.capture_id,
                        clock.iso(clock.utcnow()),
                        sid,
                        gate.CAPTURE_PENDING,
                        gate.ORDER_CREATED
                    )
                )

                audit.append(
                    conn,
                    sid,
                    "capture_completed",
                    {
                        "capture_id": summary.capture_id,
                        "amount": summary.amount,
                        "currency": summary.currency
                    }
                )

            else:
                conn.execute(
                    "UPDATE sessions SET status=? "
                    "WHERE id=? AND status IN (?,?)",
                    (
                        gate.NEEDS_RECONCILIATION,
                        sid,
                        gate.CAPTURE_PENDING,
                        gate.ORDER_CREATED
                    )
                )

                audit.append(
                    conn,
                    sid,
                    "capture_unverified",
                    {
                        "capture_status":
                            summary.status if summary else None
                    }
                )

        if not ok_capture:
            raise ApiError(
                502,
                "capture_unverified",
                "PayPal did not confirm a completed capture "
                "for the expected amount. "
                "Manual reconciliation is required."
            )

        return done(
            summary.capture_id,
            summary.amount,
            summary.currency,
            False
        )

    return app
