'use client';
import { use, useEffect, useState } from 'react';
import { endpoints, errorText, type PublicReview, type Verdict } from '@/lib/api';
import { money, levelLabel } from '@/lib/format';

export default function ReviewPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [data, setData] = useState<PublicReview | null>(null);
  const [error, setError] = useState('');
  const [done, setDone] = useState<string>('');
  useEffect(() => { endpoints.publicReview(token).then(setData).catch((e) => setError(errorText(e))); }, [token]);

  async function send(v: Verdict) {
    setError('');
    try { const r = await endpoints.submitVerdict(token, v); setDone(r.note); setData((d) => (d ? { ...d, verdict: v } : d)); } catch (e) { setError(errorText(e)); }
  }
  return (
    <main className="wrap" style={{ paddingTop: 40, maxWidth: 720 }}>
      <div className="eyebrow">Trusted-contact review</div>
      <h1 style={{ fontSize: '2.2rem' }}>A friend asked for a second opinion</h1>
      {error && <p className="err">{error}</p>}
      {data && (
        <div className="card">
          <p>Payment: <strong>{money(data.payment.amount, data.payment.currency)}</strong> to “{data.payment.merchant_label}” (not verified).</p>
          <p><span className={`pill ${data.analysis.risk_level}`}>{levelLabel(data.analysis.risk_level)}</span> &nbsp; score {data.analysis.risk_score}/100</p>
          <p>{data.analysis.explanation}</p>
          {Object.entries(data.analysis.signals).map(([k, s]) => (<div key={k} className={`sig ${s.detected ? '' : 'off'}`}><span>{s.label}</span><span>{s.detected ? 'Detected' : 'Not detected'}</span></div>))}
          <p className="note mt">{data.analysis.limitations}</p>
          {data.verdict || done ? (
            <p className="ok">Your opinion was recorded. {done}</p>
          ) : (
            <div className="row mt">
              <button className="btn primary" onClick={() => send('safe_to_proceed')}>Looks okay to me</button>
              <button className="btn danger" onClick={() => send('suspected_scam')}>I think this is a scam</button>
            </div>
          )}
          <p className="note mt">{data.note}</p>
        </div>
      )}
    </main>
  );
}
