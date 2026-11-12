"""Real PayPalGateway + order verification, driven by httpx.MockTransport (no network, no PayPal account)."""
import json

import httpx
import pytest

from secondsense.config import Settings
from secondsense.order_verification import ExpectedPayment, OrderMismatch, extract_capture, verify_order
from secondsense.paypal_gateway import PayPalError, PayPalGateway


def gw(handler, **kw):
    s = Settings(paypal_client_id="cid", paypal_client_secret="sec", **kw)
    return PayPalGateway(s, httpx.Client(transport=httpx.MockTransport(handler)))


def ok_token(request):
    return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})


def test_create_order_payload_headers_and_token_cache():
    seen = []

    def handler(req: httpx.Request):
        if req.url.path == "/v1/oauth2/token":
            seen.append("token")
            assert req.headers["authorization"].startswith("Basic ") and b"client_credentials" in req.content
            return ok_token(req)
        seen.append("order")
        assert req.headers["authorization"] == "Bearer tok" and req.headers["paypal-request-id"] == "key-1"
        body = json.loads(req.content)
        assert body["intent"] == "CAPTURE"
        unit = body["purchase_units"][0]
        assert unit["amount"] == {"currency_code": "USD", "value": "450.00"} and unit["custom_id"] == "sess"
        assert unit["payee"] == {"merchant_id": "M1"} and len(unit["description"]) <= 127
        return httpx.Response(201, json={"id": "ORDERID123456", "status": "CREATED"})

    g = gw(handler)
    for _ in range(2):
        g.create_order(amount="450.00", currency="USD", reference_id="plumber", custom_id="sess", description="x" * 300,
                       idempotency_key="key-1", payee_merchant_id="M1")
    assert seen == ["token", "order", "order"]            # access token cached between calls


def test_paypal_error_bodies_are_not_forwarded():
    def handler(req):
        if req.url.path == "/v1/oauth2/token":
            return ok_token(req)
        return httpx.Response(422, json={"name": "UNPROCESSABLE_ENTITY", "message": "SECRET-INTERNAL-DETAIL buyer@example.com",
                                         "debug_id": "abc123", "details": [{"issue": "INSTRUMENT_DECLINED", "description": "card 4111"}]})

    with pytest.raises(PayPalError) as e:
        gw(handler).capture_order("ORDERID123456", idempotency_key="k")
    err = e.value
    assert (err.code, err.paypal_status, err.issue, err.debug_id) == ("paypal_request_failed", 422, "INSTRUMENT_DECLINED", "abc123")
    assert "SECRET" not in err.message and "buyer@example.com" not in repr(err.__dict__)


def test_auth_failure_and_network_failure_and_missing_credentials():
    with pytest.raises(PayPalError) as e:
        gw(lambda r: httpx.Response(401, json={"error": "invalid_client"}))._access_token()
    assert e.value.code == "paypal_auth_failed"

    def boom(req):
        raise httpx.ConnectError("down")
    with pytest.raises(PayPalError) as e:
        gw(boom)._access_token()
    assert e.value.code == "paypal_unreachable"
    with pytest.raises(PayPalError) as e:
        PayPalGateway(Settings(), httpx.Client(transport=httpx.MockTransport(ok_token)))._access_token()
    assert e.value.code == "paypal_not_configured" and e.value.http_status == 503


# ------------------------------------------------------------------ order verification
EXP = ExpectedPayment("sess1", "ORDERID123456", "450.00", "USD", None)


def order(**over):
    o = {"id": "ORDERID123456", "intent": "CAPTURE", "status": "APPROVED",
         "purchase_units": [{"custom_id": "sess1", "amount": {"currency_code": "USD", "value": "450.00"}, "payee": {"merchant_id": "M1"}}]}
    o.update(over)
    return o


def test_verify_order_accepts_exact_match_including_decimal_formatting():
    verify_order(order(), EXP, allowed_statuses={"APPROVED"})
    o = order(); o["purchase_units"][0]["amount"]["value"] = "450"
    verify_order(o, EXP, allowed_statuses={"APPROVED"})


@pytest.mark.parametrize("mutate,code", [
    (lambda o: o.update(id="OTHERORDER123"), "order_id_mismatch"),
    (lambda o: o.update(intent="AUTHORIZE"), "order_intent_mismatch"),
    (lambda o: o.update(status="CREATED"), "order_status_invalid"),
    (lambda o: o.update(purchase_units=[]), "order_units_mismatch"),
    (lambda o: o["purchase_units"].append(o["purchase_units"][0]), "order_units_mismatch"),
    (lambda o: o["purchase_units"][0].update(custom_id="other"), "order_session_mismatch"),
    (lambda o: o["purchase_units"][0]["amount"].update(value="450.01"), "order_amount_mismatch"),
    (lambda o: o["purchase_units"][0]["amount"].update(currency_code="EUR"), "order_amount_mismatch"),
    (lambda o: o["purchase_units"][0].update(amount={}), "order_malformed"),
])
def test_verify_order_rejects_every_deviation(mutate, code):
    o = order(); mutate(o)
    with pytest.raises(OrderMismatch) as e:
        verify_order(o, EXP, allowed_statuses={"APPROVED"})
    assert e.value.code == code


def test_payee_is_enforced_only_when_configured_and_fails_closed():
    configured = ExpectedPayment("sess1", "ORDERID123456", "450.00", "USD", "M1")
    verify_order(order(), configured, allowed_statuses={"APPROVED"})
    o = order(); o["purchase_units"][0]["payee"] = {"merchant_id": "EVIL"}
    with pytest.raises(OrderMismatch):
        verify_order(o, configured, allowed_statuses={"APPROVED"})
    o["purchase_units"][0].pop("payee")
    with pytest.raises(OrderMismatch):
        verify_order(o, configured, allowed_statuses={"APPROVED"})


def test_extract_capture():
    assert extract_capture({"purchase_units": [{}]}) is None
    c = extract_capture({"purchase_units": [{"payments": {"captures": [{"id": "C1", "status": "COMPLETED", "amount": {"currency_code": "USD", "value": "5"}}]}}]})
    assert (c.capture_id, c.status, c.amount, c.currency) == ("C1", "COMPLETED", "5.00", "USD")
