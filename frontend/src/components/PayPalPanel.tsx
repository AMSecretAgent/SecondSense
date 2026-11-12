'use client';
import { useEffect, useRef, useState } from 'react';
import { endpoints, errorText, type AppConfig, type CaptureResult, type SessionView } from '@/lib/api';

interface PayPalButtons { render: (el: HTMLElement) => Promise<void>; close?: () => void }
interface PayPalNS { Buttons: (o: { createOrder: () => Promise<string>; onApprove: (d: { orderID: string }) => Promise<void>; onError: (e: unknown) => void; onCancel?: () => void }) => PayPalButtons }
declare global { interface Window { paypal?: PayPalNS } }

let sdkPromise: Promise<void> | null = null;
function loadSdk(clientId: string): Promise<void> {
  if (window.paypal) return Promise.resolve();
  sdkPromise ??= new Promise<void>((resolve, reject) => {
    const s = document.createElement('script');
    s.src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}&currency=USD&intent=capture&components=buttons`;
    s.onload = () => resolve();
    s.onerror = () => { sdkPromise = null; reject(new Error('The PayPal JS SDK failed to load.')); };
    document.body.appendChild(s);
  });
  return sdkPromise;
}

export default function PayPalPanel({ session, payments, onChanged }: { session: SessionView; payments: AppConfig['payments'] | null; onChanged: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  const [error, setError] = useState('');
  const [result, setResult] = useState<CaptureResult | null>(null);
  const sid = session.session_id;
  const allowed = session.gate.allowed && session.status !== 'captured';

  useEffect(() => {
    if (!allowed || !payments?.configured || !payments.client_id || !box.current) return;
    let alive = true; let buttons: PayPalButtons | undefined;
    const el = box.current;
    loadSdk(payments.client_id).then(async () => {
      if (!alive || !window.paypal) return;
      el.innerHTML = '';
      buttons = window.paypal.Buttons({
        // Amount and currency are NOT sent: the server prices the order from its catalog and enforces the risk gate.
        createOrder: async () => { setError(''); try { const o = await endpoints.createOrder(sid); onChanged(); return o.id; } catch (e) { setError(errorText(e)); onChanged(); throw e; } },
        onApprove: async (d) => { try { setResult(await endpoints.capture(sid, d.orderID)); } catch (e) { setError(errorText(e)); } onChanged(); },
        onError: () => setError((m) => m || 'PayPal reported an error. Nothing was captured unless shown below.'),
      });
      await buttons.render(el);
    }).catch((e) => alive && setError(errorText(e)));
    return () => { alive = false; buttons?.close?.(); };
  }, [allowed, payments, sid, onChanged]);

  return (
    <div className="card mt">
      <div className="eyebrow">Checkout · PayPal Sandbox (Orders v2, intent=CAPTURE)</div>
      <p><strong>{session.checkout.label}</strong>, priced by the server: {session.checkout.amount} {session.checkout.currency}</p>
      {session.status === 'captured' || result ? (
        <p className="ok">Capture recorded: <span className="mono">{result?.capture_id ?? session.capture_id}</span> ({payments?.environment ?? 'sandbox'}). Funds are not held in escrow.</p>
      ) : !payments?.configured ? (
        <div className="banner">PayPal Sandbox credentials are not configured on the server, so no order can be created. Add PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET to backend/.env. The live Sandbox test is pending.</div>
      ) : !session.gate.allowed ? (
        <div className="banner"><strong>Checkout is locked by the server.</strong> {session.gate.message}</div>
      ) : (<div ref={box} />)}
      {error && <p className="err">{error}</p>}
    </div>
  );
}
