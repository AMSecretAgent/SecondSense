"""Heuristic manipulation-risk engine. Pure functions, no I/O.

IMPORTANT: scores are rule-based heuristics, NOT calibrated probabilities. No false-positive/negative
rate is claimed. Design intent:
  * Urgency alone (and urgency + threat wording alone) can never reach the review/high levels.
  * "Strong" coercion categories (impersonation, secrecy, payment redirection, credential request)
    drive the level. Reaching HIGH needs at least two of them, by construction of the weights.
  * Nothing here infers merchant/charity legitimacy. Absence of signals is not evidence of safety.
  * Evidence snippets are returned to the caller for display only; use `persistable_signals` before storing.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

ENGINE_VERSION = "heuristic-2"
REVIEW_THRESHOLD = 30
HIGH_THRESHOLD = 60
NO_STRONG_CAP = 25  # without any strong category the score cannot reach REVIEW_THRESHOLD

_ENTITY = (
    r"(?:paypal|irs|internal revenue service|bank|fraud (?:department|team|desk)|security (?:team|department)"
    r"|tech(?:nical)? support|police|customs|social security(?: administration)?)"
)
_RISKWORD = (
    r"(?:alert|security|fraud|unauthori[sz]ed|suspicious|compromised|breach|verify|frozen|freeze|"
    r"suspended|locked|arrest|warrant)"
)
_SAFE_ACCOUNT = r"(?:safe(?:ty)?|secure[d]?|protected|holding|verification|temporary)"


@dataclass(frozen=True)
class Rule:
    key: str
    label: str
    weight: int
    strong: bool
    patterns: tuple[str, ...]
    skip_if_negated: bool = False


RULES: tuple[Rule, ...] = (
    Rule("impersonation", "Authority impersonation", 28, True, (
        rf"\b{_ENTITY}\b.{{0,80}}\b{_RISKWORD}\w*",
        rf"\b{_RISKWORD}\w*\b.{{0,60}}\b{_ENTITY}\b",
        rf"\b(?:this is|i am|i'm|calling from|message from)\b.{{0,40}}\b{_ENTITY}\b",
    )),
    Rule("secrecy", "Secrecy / isolation", 30, True, (
        r"\b(?:do not|don't|dont|never)\s+(?:tell|contact|call|inform|speak to|talk to|involve|alert|notify)\b"
        r".{0,30}\b(?:anyone|anybody|family|friends?|police|bank|support|supervisor|manager|others|nobody)\b",
        r"\bkeep (?:this|it|that) (?:a )?(?:secret|confidential|between us|private)\b",
        r"\bstay on the (?:line|phone|call)\b",
        r"\b(?:do not|don't|dont) hang up\b",
        r"\b(?:tell (?:no one|nobody)|(?:no one|nobody) (?:can|must|should) know)\b",
    )),
    Rule("payment_redirection", "Unusual payment destination", 25, True, (
        rf"\b{_SAFE_ACCOUNT}\s+(?:account|wallet|merchant)\b",
        r"\b(?:gift\s*cards?|crypto(?:currency)?|bitcoin|wire transfer|western union|moneygram)\b",
        r"\bfriends\s*(?:and|&)\s*family\b",
        r"\b(?:move|transfer)\s+(?:your\s+)?(?:money|funds|balance|savings)\b",
    )),
    Rule("credential_request", "Credential / code request", 30, True, (
        r"\b(?:share|read|send|give|tell|provide|enter|confirm)\b.{0,25}"
        r"\b(?:otp|one[- ]time (?:pass)?code|verification code|security code|passcode|password|pin|2fa code)\b",
    ), skip_if_negated=True),
    Rule("threat", "Threat of consequences", 14, False, (
        r"\bpermanent(?:ly)?\s+(?:freeze|frozen|ban(?:ned)?|suspend(?:ed)?|clos(?:e|ed|ure))\b",
        r"\baccount\s+(?:will\s+be\s+|is\s+|has\s+been\s+)?(?:suspended|frozen|locked|closed|terminated)\b",
        r"\b(?:arrest(?:ed)?|legal action|prosecut\w+|deport\w*)\b",
        r"\blose access\b",
    )),
    Rule("urgency", "Time pressure", 8, False, (
        r"\bwithin\s+(?:the next\s+)?\d+\s*(?:min(?:ute)?s?|hours?|hrs?)\b",
        r"\b(?:immediately|right now|right away|urgent(?:ly)?|asap|act now|last chance|final notice)\b",
    )),
)

_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None)
_PUNCT = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-"})
_NEGATION = re.compile(r"\b(?:do not|don't|dont|never|not)\s+(?:\w+\s+){0,2}$", re.I)
_COMPILED = {r.key: [re.compile(p, re.I) for p in r.patterns] for r in RULES}


def normalize(text: str) -> str:
    """NFKC + strip zero-width chars + straighten quotes, so curly apostrophes/fullwidth text can't dodge rules."""
    t = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH).translate(_PUNCT)
    return re.sub(r"\s+", " ", t).strip()


def _find(rule: Rule, text: str) -> list[str]:
    found: list[str] = []
    for rx in _COMPILED[rule.key]:
        for m in rx.finditer(text):
            if rule.skip_if_negated and _NEGATION.search(text[max(0, m.start() - 25):m.start()]):
                continue
            found.append(m.group(0)[:80])
            break
    return found


def level_for(score: int) -> str:
    return "high" if score >= HIGH_THRESHOLD else "review" if score >= REVIEW_THRESHOLD else "low"


def explanation_for(level: str) -> str:
    return {
        "high": "Several coercion indicators appear together in the text you supplied. Verify independently before paying.",
        "review": "Some warning signs in the text warrant extra verification. Checkout is not blocked.",
        "low": "No strong coercion pattern found in the supplied text. This does not verify the recipient or guarantee safety.",
    }[level]


LIMITATIONS = (
    "Rule-based heuristic on text you supplied; not a calibrated probability, fraud determination, "
    "or verification of any recipient or merchant."
)


def analyze(context: str) -> dict[str, Any]:
    text = normalize(context)
    signals: dict[str, dict[str, Any]] = {}
    for rule in RULES:
        evidence = _find(rule, text)
        detected = bool(evidence)
        signals[rule.key] = {
            "label": rule.label, "strong": rule.strong, "detected": detected,
            "points": rule.weight if detected else 0, "evidence": evidence[:2],
        }
    score = sum(s["points"] for s in signals.values())
    if not any(s["detected"] and s["strong"] for s in signals.values()):
        score = min(score, NO_STRONG_CAP)
    score = min(100, score)
    level = level_for(score)
    return {
        "engine_version": ENGINE_VERSION, "risk_score": score, "risk_level": level, "signals": signals,
        "explanation": explanation_for(level), "limitations": LIMITATIONS,
    }


def persistable_signals(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Strip message-derived evidence. Only category, detection flag and points may be stored or shared."""
    return {k: {"detected": v["detected"], "points": v["points"]} for k, v in result["signals"].items()}
