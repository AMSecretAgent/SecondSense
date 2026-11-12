import type { RiskLevel } from './api';

export const money = (amount: string, currency: string): string =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(Number(amount));

export const levelLabel = (l: RiskLevel): string => (l === 'high' ? 'Active pause' : l === 'review' ? 'Smart nudge' : 'Silent pass');

const STATUS: Record<string, string> = {
  analyzed: 'Analyzed', order_creating: 'Creating order', order_created: 'Order created', capture_pending: 'Capture pending',
  captured: 'Captured (sandbox)', needs_reconciliation: 'Needs reconciliation',
};
export const statusLabel = (s: string): string => STATUS[s] ?? s;

export const when = (iso: string): string => new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });

/** Neutralise spreadsheet formula injection in CSV exports. */
export const csvCell = (v: string): string => {
  const safe = /^[=+\-@\t\r]/.test(v) ? `'${v}` : v;
  return `"${safe.replaceAll('"', '""')}"`;
};
