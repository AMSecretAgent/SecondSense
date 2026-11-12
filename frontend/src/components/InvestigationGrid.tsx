
'use client';

import { useMemo, useState } from 'react';
import { AgGridReact } from 'ag-grid-react';
import {
  AllCommunityModule,
  ModuleRegistry,
  type ColDef,
  type RowClickedEvent,
} from 'ag-grid-community';

ModuleRegistry.registerModules([AllCommunityModule]);

type Investigation = {
  id: string;
  merchant: string;
  source: string;
  amount: number;
  currency: string;
  riskScore: number;
  riskLevel: 'High' | 'Review' | 'Low';
  status: string;
  evidence: string;
  date: string;
};

const demoRows: Investigation[] = [
  {
    id: 'SS-1001',
    merchant: 'Demo Flash Deals',
    source: 'Checkout',
    amount: 1999,
    currency: 'INR',
    riskScore: 91,
    riskLevel: 'High',
    status: 'Flagged',
    evidence:
      'Urgency pressure, unusual payment instructions and limited seller information.',
    date: '2026-11-12',
  },
  {
    id: 'SS-1002',
    merchant: 'Example Social Store',
    source: 'Instagram',
    amount: 2499,
    currency: 'INR',
    riskScore: 73,
    riskLevel: 'Review',
    status: 'Needs review',
    evidence:
      'Seller identity has not been verified. Independent buyer evidence is insufficient.',
    date: '2026-11-12',
  },
  {
    id: 'SS-1003',
    merchant: 'Demo Electronics',
    source: 'Website',
    amount: 8999,
    currency: 'INR',
    riskScore: 34,
    riskLevel: 'Low',
    status: 'Analysed',
    evidence:
      'No strong manipulation signals found in the provided checkout text.',
    date: '2026-11-11',
  },
  {
    id: 'SS-1004',
    merchant: 'Sample Reward Page',
    source: 'Browser Extension',
    amount: 0,
    currency: 'INR',
    riskScore: 95,
    riskLevel: 'High',
    status: 'Flagged',
    evidence:
      'Reward claim combined with personal-data collection and forwarding instructions.',
    date: '2026-11-11',
  },
  {
    id: 'SS-1005',
    merchant: 'Example Fashion Seller',
    source: 'Website',
    amount: 1599,
    currency: 'INR',
    riskScore: 58,
    riskLevel: 'Review',
    status: 'Needs review',
    evidence:
      'Incomplete seller details. Additional independent evidence recommended.',
    date: '2026-11-10',
  },
];

export default function InvestigationGrid() {
  const [rows] = useState<Investigation[]>(demoRows);
  const [selected, setSelected] = useState<Investigation | null>(null);
  const [search, setSearch] = useState('');
  const [riskFilter, setRiskFilter] = useState('All');

  const filteredRows = useMemo(
    () =>
      rows.filter((row) => {
        const matchesRisk =
          riskFilter === 'All' || row.riskLevel === riskFilter;

        const matchesSearch = [
          row.id,
          row.merchant,
          row.source,
          row.status,
          row.evidence,
        ]
          .join(' ')
          .toLowerCase()
          .includes(search.toLowerCase());

        return matchesRisk && matchesSearch;
      }),
    [rows, search, riskFilter]
  );

  const columns = useMemo<ColDef<Investigation>[]>(
    () => [
      { field: 'id', headerName: 'Case ID', minWidth: 120 },
      { field: 'merchant', headerName: 'Merchant', minWidth: 190 },
      { field: 'source', headerName: 'Source', minWidth: 150 },
      {
        field: 'amount',
        headerName: 'Amount',
        minWidth: 130,
        valueFormatter: (p) =>
          `${p.data?.currency ?? 'INR'} ${Number(p.value ?? 0).toLocaleString('en-IN')}`,
      },
      {
        field: 'riskScore',
        headerName: 'Risk Score',
        minWidth: 130,
        sort: 'desc',
        cellStyle: (p) => ({
          fontWeight: 'bold',
          color:
            Number(p.value) >= 80
              ? '#dc2626'
              : Number(p.value) >= 50
                ? '#d97706'
                : '#16a34a',
        }),
      },
      { field: 'riskLevel', headerName: 'Risk Level', minWidth: 140 },
      { field: 'status', headerName: 'Status', minWidth: 150 },
      { field: 'date', headerName: 'Date', minWidth: 130 },
    ],
    []
  );

  function exportCSV() {
    const headers = [
      'Case ID',
      'Merchant',
      'Source',
      'Amount',
      'Currency',
      'Risk Score',
      'Risk Level',
      'Status',
      'Evidence',
      'Date',
    ];

    const values = filteredRows.map((r) => [
      r.id,
      r.merchant,
      r.source,
      r.amount,
      r.currency,
      r.riskScore,
      r.riskLevel,
      r.status,
      r.evidence,
      r.date,
    ]);

    const escapeCSV = (value: unknown) => {
      const raw = String(value ?? '');
      const safe = /^[\s]*[=+\-@\t\r]/.test(raw) ? `'${raw}` : raw;
      return `"${safe.replace(/"/g, '""')}"`;
    };

    const csv = [headers, ...values]
      .map((row) => row.map(escapeCSV).join(','))
      .join('\r\n');

    const blob = new Blob([csv], {
      type: 'text/csv;charset=utf-8;',
    });

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'secondsense-investigations.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  const highCount = rows.filter((r) => r.riskLevel === 'High').length;
  const reviewCount = rows.filter((r) => r.riskLevel === 'Review').length;

  return (
    <main
      style={{
        maxWidth: 1440,
        margin: '0 auto',
        padding: '36px 24px',
        color: '#e2e8f0',
      }}
    >
      <div style={{ marginBottom: 28 }}>
        <p style={{ color: '#38bdf8', fontWeight: 700, letterSpacing: 2 }}>
          SECOND SENSE / INTELLIGENCE
        </p>

        <h1 style={{ fontSize: 36, fontWeight: 800, margin: '12px 0' }}>
          Fraud Investigation Dashboard
        </h1>

        <p style={{ color: '#94a3b8' }}>
          Explore transaction risks, merchant signals and supporting evidence.
        </p>

        <p style={{ color: '#fbbf24', marginTop: 10 }}>
          DEMO DATA — These are fictional investigations, not verified fraud reports.
        </p>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 16,
          marginBottom: 24,
        }}
      >
        {[
          { label: 'Total Investigations', value: rows.length },
          { label: 'High Risk', value: highCount },
          { label: 'Needs Review', value: reviewCount },
          { label: 'Visible Results', value: filteredRows.length },
        ].map((stat) => (
          <div
            key={stat.label}
            style={{
              padding: 22,
              background: '#111827',
              border: '1px solid #334155',
              borderRadius: 14,
            }}
          >
            <p style={{ color: '#94a3b8', marginBottom: 10 }}>
              {stat.label}
            </p>
            <strong style={{ fontSize: 32 }}>{stat.value}</strong>
          </div>
        ))}
      </div>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 12,
          marginBottom: 18,
        }}
      >
        <input
          type="search"
          placeholder="Search merchant, case or evidence..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            flex: '1 1 260px',
            padding: 12,
            borderRadius: 8,
            border: '1px solid #475569',
            background: '#111827',
            color: 'white',
          }}
        />

        <select
          value={riskFilter}
          onChange={(e) => setRiskFilter(e.target.value)}
          style={{
            padding: 12,
            borderRadius: 8,
            border: '1px solid #475569',
            background: '#111827',
            color: 'white',
          }}
        >
          <option value="All">All risks</option>
          <option value="High">High risk</option>
          <option value="Review">Needs review</option>
          <option value="Low">Low risk</option>
        </select>

        <button
          onClick={exportCSV}
          style={{
            padding: '12px 18px',
            background: '#2563eb',
            color: 'white',
            border: 0,
            borderRadius: 8,
            cursor: 'pointer',
            fontWeight: 700,
          }}
        >
          Export CSV
        </button>
      </div>

      <div className="ag-theme-quartz-dark" style={{ height: 430, width: '100%' }}>
        <AgGridReact<Investigation>
          rowData={filteredRows}
          columnDefs={columns}
          defaultColDef={{
            sortable: true,
            filter: true,
            resizable: true,
            flex: 1,
          }}
          pagination
          paginationPageSize={10}
          paginationPageSizeSelector={[10, 20, 50]}
          rowSelection={{ mode: 'singleRow', enableClickSelection: true }}
          onRowClicked={(event: RowClickedEvent<Investigation>) =>
            setSelected(event.data ?? null)
          }
          theme="legacy"
        />
      </div>

      <section
        style={{
          marginTop: 24,
          padding: 24,
          background: '#111827',
          border: '1px solid #334155',
          borderRadius: 14,
        }}
      >
        <h2 style={{ fontSize: 22, fontWeight: 700 }}>
          Investigation Evidence
        </h2>

        {!selected ? (
          <p style={{ color: '#94a3b8', marginTop: 12 }}>
            Select a row to inspect its risk signals and evidence.
          </p>
        ) : (
          <div style={{ marginTop: 18, lineHeight: 2 }}>
            <p><strong>Case:</strong> {selected.id}</p>
            <p><strong>Merchant:</strong> {selected.merchant}</p>
            <p><strong>Risk Score:</strong> {selected.riskScore}/100</p>
            <p><strong>Risk Level:</strong> {selected.riskLevel}</p>
            <p><strong>Status:</strong> {selected.status}</p>
            <p><strong>Evidence:</strong> {selected.evidence}</p>
          </div>
        )}
      </section>
    </main>
  );
}
