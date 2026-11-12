
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  endpoints,
  errorText,
  type AppConfig,
  type SessionView,
} from "@/lib/api";
import WarningGate from "./WarningGate";
import PayPalPanel from "./PayPalPanel";

export default function Workspace() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [context, setContext] = useState("");
  const [itemId, setItemId] = useState("");
  const [session, setSession] = useState<SessionView | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    endpoints.config()
      .then((data) => {
        setConfig(data);
        if (data.items.length) setItemId(data.items[0].id);
      })
      .catch((e) => setError(errorText(e)));
  }, []);

  const refreshSession = useCallback(async () => {
    if (!session) return;
    try {
      setSession(await endpoints.session(session.session_id));
    } catch (e) {
      setError(errorText(e));
    }
  }, [session?.session_id]);

  async function analyze() {
    if (!context.trim() || !itemId) return;

    setLoading(true);
    setError("");
    setSession(null);

    try {
      const result = await endpoints.analyze(context, itemId);
      setSession(result);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }

  const riskColor =
    session?.risk.effective_level === "high"
      ? "#dc2626"
      : session?.risk.effective_level === "review"
      ? "#d97706"
      : "#16a34a";

  return (
    <main
      style={{
        maxWidth: 1000,
        margin: "0 auto",
        padding: "40px 24px",
        color: "#14233d",
      }}
    >
      <div style={{ marginBottom: 30 }}>
        <p
          style={{
            fontSize: 12,
            fontWeight: 800,
            letterSpacing: 2,
            color: "#1769e0",
          }}
        >
          SECONDSENSE / PROTECTED CHECKOUT
        </p>

        <h1 style={{ fontSize: 38, margin: "12px 0" }}>
          Think twice. Pay safely.
        </h1>

        <p style={{ color: "#64748b", lineHeight: 1.7 }}>
          Tell SecondSense about the payment request.
          We&apos;ll check for suspicious signals before
          you proceed to PayPal Sandbox.
        </p>
      </div>

      <section
        style={{
          background: "#fff",
          border: "1px solid #e2e8f0",
          borderRadius: 18,
          padding: 28,
          marginBottom: 24,
        }}
      >
        <h2 style={{ marginTop: 0, fontSize: 22 }}>
          1. Choose a payment scenario
        </h2>

        <label
          htmlFor="checkout-item"
          style={{ display: "block", marginBottom: 10 }}
        >
          Payment type
        </label>

        <select
          id="checkout-item"
          value={itemId}
          onChange={(e) => {
            setItemId(e.target.value);
            setSession(null);
          }}
          disabled={!config}
          style={{
            width: "100%",
            padding: 14,
            border: "1px solid #cbd5e1",
            borderRadius: 10,
            background: "white",
            color: "#14233d",
            marginBottom: 20,
          }}
        >
          {config?.items.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label} — {item.amount} {item.currency}
            </option>
          ))}
        </select>

        <label
          htmlFor="payment-context"
          style={{ display: "block", marginBottom: 10 }}
        >
          What did the seller or requester tell you?
        </label>

        <textarea
          id="payment-context"
          value={context}
          onChange={(e) => {
            setContext(e.target.value);
            setSession(null);
          }}
          placeholder="Example: Someone claiming to be PayPal support says my account will be blocked unless I send $1,200 immediately."
          rows={5}
          style={{
            width: "100%",
            padding: 15,
            border: "1px solid #cbd5e1",
            borderRadius: 10,
            background: "white",
            color: "#14233d",
            resize: "vertical",
            fontFamily: "inherit",
            fontSize: 15,
          }}
        />

        <button
          type="button"
          onClick={analyze}
          disabled={loading || !config || !itemId || !context.trim()}
          style={{
            marginTop: 18,
            background: "#1769e0",
            color: "white",
            border: 0,
            borderRadius: 10,
            padding: "14px 24px",
            fontWeight: 700,
            cursor: "pointer",
            opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? "Analyzing..." : "Analyze payment risk"}
        </button>

        {error && (
          <p role="alert" style={{ color: "#dc2626", marginTop: 15 }}>
            {error}
          </p>
        )}
      </section>

      {session && (
        <>
          <section
            style={{
              background: "white",
              border: "1px solid #e2e8f0",
              borderRadius: 18,
              padding: 28,
              marginBottom: 24,
            }}
          >
            <h2 style={{ marginTop: 0 }}>
              2. Your risk assessment
            </h2>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 16,
                marginBottom: 20,
                flexWrap: "wrap",
              }}
            >
              <strong
                style={{
                  fontSize: 42,
                  color: riskColor,
                }}
              >
                {session.risk.score}/100
              </strong>

              <span
                style={{
                  background: riskColor,
                  color: "white",
                  padding: "8px 14px",
                  borderRadius: 30,
                  fontWeight: 700,
                  textTransform: "uppercase",
                  fontSize: 12,
                }}
              >
                {session.risk.effective_level} risk
              </span>
            </div>

            <p style={{ lineHeight: 1.7 }}>
              {session.risk.explanation}
            </p>

            <h3>Detected signals</h3>

            {Object.entries(session.risk.signals).map(
              ([key, signal]) => (
                <div
                  key={key}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 16,
                    padding: "12px 0",
                    borderBottom: "1px solid #e2e8f0",
                  }}
                >
                  <span>{signal.label}</span>
                  <strong
                    style={{
                      color: signal.detected
                        ? "#dc2626"
                        : "#16a34a",
                    }}
                  >
                    {signal.detected ? "Detected" : "Not detected"}
                  </strong>
                </div>
              )
            )}

            <p
              style={{
                color: "#64748b",
                fontSize: 12,
                marginTop: 20,
              }}
            >
              {session.risk.limitations}
            </p>
          </section>

          <section
            style={{
              background: "white",
              border: "1px solid #e2e8f0",
              borderRadius: 18,
              padding: 28,
              marginBottom: 24,
            }}
          >
            <h2 style={{ marginTop: 0 }}>
              3. Safety review
            </h2>

            <WarningGate
              session={session}
              onUpdate={setSession}
            />

            {session.gate.allowed ? (
              <p style={{ color: "#15803d" }}>
                Review requirements satisfied. You may proceed
                to the sandbox checkout. This does not guarantee
                the payment is safe.
              </p>
            ) : !session.warning ? (
              <p style={{ color: "#b45309" }}>
                Checkout is restricted: {session.gate.message}
              </p>
            ) : null}
          </section>

          <section
            style={{
              background: "white",
              border: "1px solid #e2e8f0",
              borderRadius: 18,
              padding: 28,
            }}
          >
            <h2 style={{ marginTop: 0 }}>
              4. PayPal protected payment
            </h2>

            <PayPalPanel
              session={session}
              payments={config?.payments ?? null}
              onChanged={refreshSession}
            />
          </section>
        </>
      )}

      <p
        style={{
          color: "#64748b",
          fontSize: 12,
          marginTop: 24,
        }}
      >
        Independent hackathon prototype. Payments use PayPal
        Sandbox. Risk scores are heuristic and are not
        verified fraud determinations.
      </p>
    </main>
  );
}
