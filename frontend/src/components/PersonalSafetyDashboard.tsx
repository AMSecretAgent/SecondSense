
"use client";

import { useMemo, useState } from "react";

type Payment = {
  id: number;
  merchant: string;
  amount: number;
  date: string;
  category: string;
  status: "Safe" | "Review" | "Upcoming";
  detail: string;
};

const payments: Payment[] = [
  {
    id: 1,
    merchant: "Netflix",
    amount: 649,
    date: "18 Nov 2026",
    category: "Subscription",
    status: "Upcoming",
    detail: "Recurring payment approaching. Review whether you still use this service.",
  },
  {
    id: 2,
    merchant: "Spotify",
    amount: 119,
    date: "21 Nov 2026",
    category: "Subscription",
    status: "Upcoming",
    detail: "Subscription renewal reminder.",
  },
  {
    id: 3,
    merchant: "Unfamiliar Online Store",
    amount: 2999,
    date: "12 Nov 2026",
    category: "Shopping",
    status: "Review",
    detail: "Illustrative unfamiliar merchant. Verify the seller and payment request.",
  },
  {
    id: 4,
    merchant: "Online Grocery",
    amount: 850,
    date: "10 Nov 2026",
    category: "Shopping",
    status: "Safe",
    detail: "No warning signals recorded in this fictional example.",
  },
];

const disputes = [
  {
    id: "CASE-001",
    merchant: "Unfamiliar Online Store",
    issue: "Item not received",
    status: "Evidence collection",
  },
];

const formatMoney = (value: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);

export default function PersonalSafetyDashboard() {
  const [filter, setFilter] = useState("All");
  const [selected, setSelected] = useState<Payment | null>(null);

  const visible = useMemo(
    () =>
      payments.filter(
        (p) => filter === "All" || p.status === filter
      ),
    [filter]
  );

  const upcoming = payments.filter(
    (p) => p.status === "Upcoming"
  );
  const flagged = payments.filter(
    (p) => p.status === "Review"
  );

  return (
    <main className="ss-dashboard">
      <style>{`
        .ss-dashboard {
          min-height: 100vh;
          padding: 42px max(24px, calc((100vw - 1180px)/2));
          background: #f5f7fb;
          color: #14233d;
          font-family: Arial, sans-serif;
        }
        .ss-dashboard * { box-sizing: border-box; }
        .ss-eyebrow {
          color: #1769df;
          font-size: 12px;
          font-weight: 800;
          letter-spacing: 2px;
        }
        .ss-dashboard h1 {
          font-size: clamp(28px, 4vw, 40px);
          margin: 12px 0;
          color: #10213c;
        }
        .ss-dashboard h2 {
          font-size: 19px;
          color: #14233d;
          margin: 0 0 16px;
        }
        .ss-muted { color: #63728b; line-height: 1.6; }
        .ss-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 16px;
          margin: 28px 0;
        }
        .ss-card {
          background: white;
          border: 1px solid #e1e7f0;
          border-radius: 16px;
          padding: 22px;
          box-shadow: 0 3px 14px #14233d08;
        }
        .ss-number {
          font-size: 30px;
          font-weight: 800;
          margin-top: 12px;
        }
        .ss-columns {
          display: grid;
          grid-template-columns: 1.6fr 1fr;
          gap: 20px;
          margin-bottom: 20px;
        }
        .ss-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 12px;
          padding: 16px 0;
          border-bottom: 1px solid #e9edf4;
        }
        .ss-row:last-child { border-bottom: none; }
        .ss-pill {
          font-size: 12px;
          font-weight: 700;
          border-radius: 30px;
          padding: 7px 11px;
          white-space: nowrap;
        }
        .ss-safe { background: #e8f8ee; color: #14763b; }
        .ss-review { background: #fff0e5; color: #b35112; }
        .ss-upcoming { background: #eaf1ff; color: #245dc5; }
        .ss-button {
          background: #1769e0;
          color: white;
          padding: 11px 16px;
          border: none;
          border-radius: 9px;
          font-weight: 700;
          cursor: pointer;
          text-decoration: none;
          display: inline-block;
          font-size: 13px;
        }
        .ss-secondary {
          background: #edf3fc;
          color: #2459a5;
        }
        .ss-select {
          border: 1px solid #d8e0ed;
          border-radius: 9px;
          padding: 9px;
          background: white;
          color: #14233d;
        }
        .ss-demo {
          background: #fff7e8;
          border: 1px solid #f0d6a0;
          padding: 12px 16px;
          border-radius: 10px;
          color: #80530b;
          font-size: 13px;
          margin-top: 20px;
        }
        @media (max-width: 900px) {
          .ss-grid { grid-template-columns: repeat(2, 1fr); }
          .ss-columns { grid-template-columns: 1fr; }
        }
        @media (max-width: 520px) {
          .ss-grid { grid-template-columns: 1fr; }
          .ss-dashboard { padding: 24px 16px; }
        }
      `}</style>

      <div className="ss-eyebrow">SECONDSENSE / YOUR SAFETY HUB</div>
      <h1>Your money. Your control.</h1>
      <p className="ss-muted">
        Stay aware of recurring payments, review suspicious activity,
        and organize payment issues in one place.
      </p>

      <div className="ss-demo">
        Demo mode: All payments, merchants and disputes shown below are
        fictional examples, not data from your PayPal account.
      </div>

      <div className="ss-grid">
        {[
          ["Payments tracked", payments.length],
          ["Upcoming renewals", upcoming.length],
          ["Needs attention", flagged.length],
          ["Open dispute cases", disputes.length],
        ].map(([label, value]) => (
          <div className="ss-card" key={label}>
            <div className="ss-muted">{label}</div>
            <div className="ss-number">{value}</div>
          </div>
        ))}
      </div>

      <div className="ss-columns">
        <section className="ss-card">
          <h2>Upcoming payments</h2>
          <p className="ss-muted">
            Remember what is renewing before the next charge.
          </p>
          {upcoming.map((p) => (
            <div className="ss-row" key={p.id}>
              <div>
                <strong>{p.merchant}</strong>
                <div className="ss-muted">{p.date}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <strong>{formatMoney(p.amount)}</strong>
                <div>
                  <span className="ss-pill ss-upcoming">
                    Renewal
                  </span>
                </div>
              </div>
            </div>
          ))}
        </section>

        <section className="ss-card">
          <h2>Safety alerts</h2>
          <p className="ss-muted">
            Payments or requests that deserve another look.
          </p>
          {flagged.map((p) => (
            <div className="ss-row" key={p.id}>
              <div>
                <strong>{p.merchant}</strong>
                <div className="ss-muted">
                  {formatMoney(p.amount)}
                </div>
              </div>
              <button
                className="ss-button"
                onClick={() => setSelected(p)}
              >
                Review
              </button>
            </div>
          ))}
          <a className="ss-button ss-secondary" href="/checkout">
            Open protected checkout
          </a>
        </section>
      </div>

      <section className="ss-card" style={{ marginBottom: 20 }}>
        <div className="ss-row" style={{ paddingTop: 0 }}>
          <h2 style={{ margin: 0 }}>Payment activity</h2>
          <select
            className="ss-select"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            aria-label="Filter payment activity"
          >
            <option>All</option>
            <option>Safe</option>
            <option>Review</option>
            <option>Upcoming</option>
          </select>
        </div>

        {visible.map((p) => (
          <div className="ss-row" key={p.id}>
            <div>
              <strong>{p.merchant}</strong>
              <div className="ss-muted">
                {p.category} · {p.date}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <strong>{formatMoney(p.amount)}</strong>
              <div style={{ marginTop: 8 }}>
                <span
                  className={`ss-pill ${
                    p.status === "Safe"
                      ? "ss-safe"
                      : p.status === "Review"
                      ? "ss-review"
                      : "ss-upcoming"
                  }`}
                >
                  {p.status}
                </span>
              </div>
              <button
                onClick={() => setSelected(p)}
                style={{
                  background: "none",
                  border: "none",
                  color: "#1769e0",
                  cursor: "pointer",
                  marginTop: 8,
                }}
              >
                View details
              </button>
            </div>
          </div>
        ))}
      </section>

      <section className="ss-card">
        <h2>Dispute companion</h2>
        <p className="ss-muted">
          Keep track of payment problems and prepare supporting evidence.
        </p>
        {disputes.map((d) => (
          <div className="ss-row" key={d.id}>
            <div>
              <strong>{d.merchant}</strong>
              <div className="ss-muted">
                {d.id} · {d.issue}
              </div>
              <span className="ss-pill ss-upcoming">
                {d.status}
              </span>
            </div>
            <a
              href="https://www.paypal.com/in/webapps/mpp/buyer-dispute-resolution"
              target="_blank"
              rel="noopener noreferrer"
              className="ss-button ss-secondary"
            >
              PayPal Resolution Centre
            </a>
          </div>
        ))}
        <p className="ss-muted" style={{ fontSize: 12 }}>
          Demo cases are not actual PayPal disputes. SecondSense
          does not submit or manage PayPal disputes automatically.
        </p>
      </section>

      {selected && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Payment details"
          style={{
            position: "fixed",
            inset: 0,
            background: "#0009",
            display: "grid",
            placeItems: "center",
            padding: 20,
            zIndex: 1000,
          }}
        >
          <div
            className="ss-card"
            style={{ width: "100%", maxWidth: 450 }}
          >
            <h2>{selected.merchant}</h2>
            <p className="ss-muted">{selected.detail}</p>
            <p>
              <strong>{formatMoney(selected.amount)}</strong>
            </p>
            <p>Status: {selected.status}</p>
            <button
              className="ss-button"
              onClick={() => setSelected(null)}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
