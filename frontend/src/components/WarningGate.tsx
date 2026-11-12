'use client';
import { useEffect, useState } from 'react';
import { endpoints, errorText, type SessionView } from '@/lib/api';

export default function WarningGate({ session, onUpdate }: { session: SessionView; onUpdate: (s: SessionView) => void }) {
  const w = session.warning;
  const [left, setLeft] = useState(w?.pause_remaining_seconds ?? 0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    setLeft(w?.pause_remaining_seconds ?? 0);
    const t = setInterval(() => setLeft((x) => Math.max(0, x - 1)), 1000);
    return () => clearInterval(t);
  }, [w?.pause_remaining_seconds, w?.digest, session.status]);
  if (!w || session.gate.allowed) return null;
  const total = w.min_pause_seconds || 1;

  async function acknowledge() {
    if (!w) return;
    setBusy(true); setError('');
    try { onUpdate(await endpoints.acknowledge(session.session_id, w.digest)); }
    catch (e) { setError(errorText(e)); try { onUpdate(await endpoints.session(session.session_id)); } catch { /* keep showing the error */ } }
    finally { setBusy(false); }
  }
  return (
    <div className="warn" role="alert">
      <h3>{w.title}</h3>
      <ul>{w.points.map((p) => <li key={p}>{p}</li>)}</ul>
      <div className="meter" aria-hidden><div style={{ width: `${Math.round(((total - left) / total) * 100)}%` }} /></div>
      <button className="btn danger" disabled={left > 0 || busy} onClick={acknowledge}>{left > 0 ? `Pause: ${left}s` : 'I have read this and choose to continue'}</button>
      <p className="note mt">The server measures this pause. Acknowledging does not mean the payment is safe.</p>
      {error && <p className="err">{error}</p>}
    </div>
  );
}
