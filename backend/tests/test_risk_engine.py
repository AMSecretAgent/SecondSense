"""Risk engine: legitimate urgency is tested separately from coercive impersonation."""
import itertools
import json

import pytest

from secondsense import risk_engine as re_
from secondsense.risk_engine import analyze, persistable_signals

STRONG = {r.key for r in re_.RULES if r.strong}

# --- legitimate urgency: must stay low / frictionless -------------------------------------------------------------
LEGIT = [
    "Emergency plumber invoice #408: burst pipe repair, $450 due today so the technician can dispatch.",
    "URGENT: burst pipe in the basement, emergency plumber needs payment within 2 hours so the technician can dispatch.",
    "My landlord says rent is due within 24 hours or a late fee applies. Sending $1,500 for rent.",
    "Please send $1,500 today for rent, thanks.",
    "Final notice from the electric utility: invoice due immediately to avoid a late fee.",
    "Pay $35 for coffee and breakfast at the local cafe.",
    "ASAP please, the florist needs the $80 deposit right now to hold Saturday's delivery slot.",
]


@pytest.mark.parametrize("text", LEGIT)
def test_legitimate_urgency_is_not_flagged(text):
    r = analyze(text)
    assert r["risk_level"] == "low", (r["risk_score"], text)
    assert r["risk_score"] <= re_.NO_STRONG_CAP
    assert not any(s["detected"] for k, s in r["signals"].items() if k in STRONG)


def test_urgency_is_detected_but_cannot_create_friction_alone():
    r = analyze("URGENT!! Pay immediately, within 10 minutes, act now, final notice, asap")
    assert r["signals"]["urgency"]["detected"]
    assert r["risk_level"] == "low"


def test_urgency_plus_threat_wording_alone_stays_below_review():
    r = analyze("Your account will be suspended immediately. Permanently frozen. You will lose access. Act now, within 5 minutes.")
    assert r["signals"]["threat"]["detected"] and r["signals"]["urgency"]["detected"]
    assert r["risk_score"] <= re_.NO_STRONG_CAP and r["risk_level"] == "low"


# --- coercive impersonation: must escalate ------------------------------------------------------------------------
def test_coercive_paypal_impersonation_is_high():
    r = analyze("PayPal fraud department security alert: your account will be permanently frozen. Move $1200 to our "
                "safety account within 15 minutes. Do not contact support or tell anyone.")
    assert r["risk_level"] == "high" and r["risk_score"] >= re_.HIGH_THRESHOLD
    for key in ("impersonation", "secrecy", "payment_redirection", "threat", "urgency"):
        assert r["signals"][key]["detected"], key


def test_wildfire_style_request_is_high_without_judging_charity_status():
    r = analyze("URGENT wildfire relief donation! Send $200 immediately to our secure holding account. "
                "We are the official disaster relief charity. Do not contact anyone.")
    assert r["risk_level"] == "high"
    assert "charity" not in json.dumps({k: v["label"] for k, v in r["signals"].items()}).lower()
    assert not r["signals"]["impersonation"]["detected"]  # the claim "official charity" is not verified or scored as identity


def test_impersonation_plus_urgency_is_review_not_high():
    r = analyze("PayPal security alert: please verify your account immediately.")
    assert r["risk_level"] == "review"


def test_credential_request_detected_but_security_advice_is_not():
    assert analyze("Read me the verification code we just texted you.")["signals"]["credential_request"]["detected"]
    assert not analyze("Never share your one-time code or password with anyone.")["signals"]["credential_request"]["detected"]
    assert not analyze("Do not share your PIN.")["signals"]["credential_request"]["detected"]


def test_same_urgency_text_differs_only_by_coercive_content():
    base = "Pay $450 immediately so the technician can dispatch."
    assert analyze(base)["risk_level"] == "low"
    coerced = base + " This is the PayPal security team. Do not tell anyone and move the funds to a safe account."
    assert analyze(coerced)["risk_level"] == "high"


# --- robustness ---------------------------------------------------------------------------------------------------
def test_curly_quotes_and_zero_width_characters_do_not_evade_rules():
    assert analyze("PayPal security team: Don\u2019t tell anyone.")["signals"]["secrecy"]["detected"]
    assert analyze("do\u200b not tell anyone about this")["signals"]["secrecy"]["detected"]
    assert analyze("\uff30\uff41\uff59\uff30\uff41\uff4c security alert")["signals"]["impersonation"]["detected"]  # fullwidth


SAMPLES = {
    "impersonation": "This is the PayPal fraud team.",
    "secrecy": "Do not tell anyone.",
    "payment_redirection": "Move your funds to a safety account.",
    "credential_request": "Read me the verification code.",
    "threat": "Your account will be suspended.",
    "urgency": "Do it immediately.",
}


def test_invariants_hold_for_every_combination_of_signals():
    for n in range(0, len(SAMPLES) + 1):
        for combo in itertools.combinations(SAMPLES, n):
            r = analyze(" ".join(SAMPLES[k] for k in combo))
            strong = {k for k in combo if k in STRONG}
            assert 0 <= r["risk_score"] <= 100
            if not strong:
                assert r["risk_level"] == "low", combo          # urgency/threat can never trigger friction alone
            if r["risk_level"] == "high":
                assert len(strong) >= 2, combo                   # high always needs two strong coercion categories
            assert r["risk_level"] == re_.level_for(r["risk_score"])


def test_analysis_is_deterministic():
    t = "PayPal security alert, do not tell anyone, move $500 to a safe account"
    assert analyze(t) == analyze(t)


# --- privacy ------------------------------------------------------------------------------------------------------
def test_persistable_signals_contain_no_message_text():
    text = "PayPal fraud department security alert: Do not contact support or tell anyone. Move $1200 to our safety account."
    r = analyze(text)
    assert any(v["evidence"] for v in r["signals"].values())            # evidence exists for transient display...
    stored = persistable_signals(r)
    assert set(next(iter(stored.values()))) == {"detected", "points"}   # ...but is stripped before storage/sharing
    blob = json.dumps(stored).lower()
    assert "fraud department" not in blob and "support" not in blob and "$1200" not in blob


def test_limitations_state_heuristic_nature():
    r = analyze("hello there")
    assert "not a calibrated probability" in r["limitations"]
    assert r["engine_version"].startswith("heuristic")


def test_no_strong_signal_cap_holds_even_if_weights_are_retuned(monkeypatch):
    """The cap is a structural guarantee, not an accident of today's weights."""
    import dataclasses
    inflated = tuple(dataclasses.replace(r, weight=90) if not r.strong else r for r in re_.RULES)
    monkeypatch.setattr(re_, "RULES", inflated)
    r = analyze("URGENT! Act now, within 5 minutes! Your account will be permanently suspended. Final notice.")
    assert r["signals"]["urgency"]["detected"] and r["signals"]["threat"]["detected"]
    assert r["risk_score"] == re_.NO_STRONG_CAP and r["risk_level"] == "low"
