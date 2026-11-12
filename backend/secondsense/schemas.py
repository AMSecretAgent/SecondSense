"""Request bodies. extra="forbid" everywhere: unknown fields (e.g. a legacy `acknowledged_risk`) are rejected."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated

SessionId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{16,64}$")]
ItemId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,40}$")]


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AnalyzeIn(_Body):
    context: str = Field(min_length=5, max_length=5000)
    checkout_item_id: ItemId


class AcknowledgeIn(_Body):
    warning_digest: str = Field(min_length=8, max_length=64)
    confirm: Literal[True]


class ReviewCreateIn(_Body):
    session_id: SessionId
    consent: bool


class VerdictIn(_Body):
    verdict: Literal["safe_to_proceed", "suspected_scam"]


class OrderIn(_Body):
    session_id: SessionId


class CaptureIn(_Body):
    session_id: SessionId
