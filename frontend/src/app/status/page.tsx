import { STATUS, type Maturity } from '@/lib/status';

const TITLES: Record<Maturity, string> = { working: 'Working', simulated: 'Simulated / demo data', pending: 'Pending / not built' };

export default function StatusPage() {
  return (
    <main className="wrap" style={{ paddingTop: 40 }}>
      <h1 style={{ fontSize: '2.4rem' }}>Project status</h1>
      <p className="note">Nothing here claims a live PayPal transaction unless you have run one with your own Sandbox credentials.</p>
      {(Object.keys(TITLES) as Maturity[]).map((k) => (
        <section key={k} className="card mt">
          <h2>{TITLES[k]}</h2>
          {STATUS[k].map((s) => (<div className="sig" key={s.name}><div><strong>{s.name}</strong><div className="note">{s.detail}</div></div></div>))}
        </section>
      ))}
    </main>
  );
}
