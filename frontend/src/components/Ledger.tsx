'use client';
import { useEffect, useState } from 'react';
import { endpoints, errorText, type LedgerRow } from '@/lib/api';
import { csvCell, levelLabel, money, statusLabel, when } from '@/lib/format';

export default function Ledger({ refreshKey }: { refreshKey: number }) {
  const [rows, setRows] = useState<LedgerRow[]>([]);
  const [error, setError] = useState('');
  useEffect(() => { endpoints.sessions().then(setRows).catch((e) => setError(errorText(e))); }, [refreshKey]);

  function exportCsv() {
    const head = ['time', 'item', 'amount', 'currency', 'risk_score', 'effective_level', 'status', 'acknowledged', 'capture_id'];
    const lines = rows.map((r) => [r.created_at, r.item_label, r.amount, r.currency, String(r.risk_score), r.effective_level, r.status, String(r.acknowledged), r.capture_id ?? ''].map(csvCell).join(','));
    const url = URL.createObjectURL(new Blob([[head.map(csvCell).join(','), ...lines].join('\n')], { type: 'text/csv' }));
    const a = document.createElement('a'); a.href = url; a.download = 'secondsense-ledger.csv'; a.click(); URL.revokeObjectURL(url);
  }
  return (
    <section className="card mt">
      <div className="row"><h2 style={{ margin: 0 }}>Session ledger</h2><span className="spacer" /><button className="btn sm" disabled={!rows.length} onClick={exportCsv}>Export CSV</button></div>
      <p className="note">Only signal categories and scores are stored, never the message text. Scoped to this browser by a random key (not a user identity).</p>
      {error && <p className="err">{error}</p>}
      <div className="scroll"><table>
        <thead><tr><th>When</th><th>Item</th><th>Amount</th><th>Risk</th><th>Signals</th><th>Status</th></tr></thead>
        <tbody>
          {rows.length === 0 && <tr><td colSpan={6} className="note">No sessions yet.</td></tr>}
          {rows.map((r) => (
            <tr key={r.session_id}>
              <td>{when(r.created_at)}</td><td>{r.item_label}</td><td>{money(r.amount, r.currency)}</td>
              <td><span className={`pill ${r.effective_level}`}>{levelLabel(r.effective_level)}</span> {r.risk_score}</td>
              <td>{r.signals.map((s) => s.label).join(', ') || '-'}</td>
              <td>{statusLabel(r.status)}{r.acknowledged ? ' · acknowledged' : ''}</td>
            </tr>
          ))}
        </tbody>
      </table></div>
    </section>
  );
}
