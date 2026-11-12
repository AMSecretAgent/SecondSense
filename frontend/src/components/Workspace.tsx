
'use client';

import { useState } from 'react';
import InvestigationGrid from './InvestigationGrid';

export default function Workspace() {
  const [activeTab, setActiveTab] = useState<'overview' | 'investigations'>('overview');

  return (
    <main style={{ maxWidth: 1400, margin: '0 auto', padding: '32px 24px' }}>
      <div style={{ marginBottom: 28 }}>
        <p style={{ fontSize: 13, fontWeight: 700, letterSpacing: 2 }}>
          SECONDSENSE / AI-POWERED FRAUD PROTECTION
        </p>

        <h1 style={{ fontSize: 36, margin: '12px 0' }}>
          Your second sense against scams.
        </h1>

        <p>
          Analyse suspicious shopping links, identify manipulation signals,
          and review payment risks before making a decision.
        </p>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
        <button
          className="btn"
          onClick={() => setActiveTab('overview')}
          aria-pressed={activeTab === 'overview'}
        >
          Overview
        </button>

        <button
          className="btn"
          onClick={() => setActiveTab('investigations')}
          aria-pressed={activeTab === 'investigations'}
        >
          Fraud Intelligence
        </button>
      </div>

      {activeTab === 'overview' ? (
        <section className="card">
          <h2>SecondSense Protection</h2>
          <p>
            Check suspicious websites and shopping offers using the
            SecondSense browser extension.
          </p>
          <p>
            The fraud intelligence dashboard lets you inspect risk signals
            and investigation evidence.
          </p>
        </section>
      ) : (
        <InvestigationGrid />
      )}
    </main>
  );
}
