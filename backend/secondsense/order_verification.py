"""Server-side verification of a PayPal order against what the server expected. Fails closed."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


class OrderMismatch(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ExpectedPayment:
    session_id: str
    order_id: str
    amount: str
    currency: str
    merchant_id: str | None = None


@dataclass(frozen=True)
class CaptureSummary:
    capture_id: str
    status: str
    amount: str
    currency: str


def _money(value: Any) -> str:
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError):
        raise OrderMismatch("order_malformed", "PayPal order amount is malformed.")


def verify_order(order: dict[str, Any], exp: ExpectedPayment, *, allowed_statuses: set[str]) -> None:
    if order.get("id") != exp.order_id:
        raise OrderMismatch("order_id_mismatch", "PayPal returned a different order.")
    if order.get("intent") != "CAPTURE":
        raise OrderMismatch("order_intent_mismatch", "Order intent is not CAPTURE.")
    if order.get("status") not in allowed_statuses:
        raise OrderMismatch("order_status_invalid", "The order has not been approved by the buyer.")
    units = order.get("purchase_units")
    if not isinstance(units, list) or len(units) != 1 or not isinstance(units[0], dict):
        raise OrderMismatch("order_units_mismatch", "Order must contain exactly one purchase unit.")
    unit = units[0]
    if unit.get("custom_id") != exp.session_id:
        raise OrderMismatch("order_session_mismatch", "This order does not belong to this session.")
    amt = unit.get("amount")
    if not isinstance(amt, dict) or "value" not in amt or "currency_code" not in amt:
        raise OrderMismatch("order_malformed", "PayPal order amount is missing.")
    expected_value = str(Decimal(exp.amount).quantize(Decimal("0.01")))
    if (_money(amt["value"]), amt["currency_code"]) != (expected_value, exp.currency):
        raise OrderMismatch("order_amount_mismatch", "Order amount or currency differs from the server price.")
    if exp.merchant_id:
        payee = unit.get("payee")
        if not isinstance(payee, dict) or payee.get("merchant_id") != exp.merchant_id:
            raise OrderMismatch("order_payee_mismatch", "Order payee is not the configured merchant.")


def extract_capture(order: dict[str, Any]) -> CaptureSummary | None:
    try:
        cap = order["purchase_units"][0]["payments"]["captures"][0]
        return CaptureSummary(str(cap["id"]), str(cap["status"]), _money(cap["amount"]["value"]), str(cap["amount"]["currency_code"]))
    except (KeyError, IndexError, TypeError, OrderMismatch):
        return None
