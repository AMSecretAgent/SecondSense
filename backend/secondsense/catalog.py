"""Server-owned checkout catalog and the high-risk warning text. Clients choose an item id; they never set price or currency."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal

HIGH_RISK_WARNING_VERSION = "2026-11-v1"
HIGH_RISK_WARNING_TITLE = "Pause: this request shows several pressure patterns"
HIGH_RISK_WARNING_POINTS = (
    "Scammers create urgency, secrecy and fear so you act before you think.",
    "Do not use phone numbers or links from the message. Contact the organisation through a channel you already trust.",
    "No genuine company asks you to move money to a 'safe' or 'holding' account.",
    "Payments to people or organisations you cannot independently verify are hard to recover.",
    "This is a heuristic warning, not proof of fraud. Continuing is your decision.",
)

MERCHANT = {
    "id": "secondsense-demo-merchant",
    "name": "SecondSense Demo Merchant",
    "verified": False,
    "note": "Demo merchant for the sandbox. SecondSense does not verify merchants or charities.",
}


@dataclass(frozen=True)
class Item:
    id: str
    label: str
    amount: Decimal
    currency: str = "USD"

    @property
    def amount_str(self) -> str:
        return str(self.amount.quantize(Decimal("0.01")))


CATALOG: dict[str, Item] = {i.id: i for i in (
    Item("coffee", "Coffee and breakfast", Decimal("35.00")),
    Item("plumber", "Emergency plumber invoice #408", Decimal("450.00")),
    Item("relief_donation", "Wildfire relief donation", Decimal("200.00")),
    Item("safety_transfer", "Account 'safety' transfer", Decimal("1200.00")),
)}


def warning_digest() -> str:
    """Stable digest of the exact warning text issued; acknowledgments are bound to it."""
    blob = "\n".join([HIGH_RISK_WARNING_VERSION, HIGH_RISK_WARNING_TITLE, *HIGH_RISK_WARNING_POINTS])
    return hashlib.sha256(blob.encode()).hexdigest()[:32]
