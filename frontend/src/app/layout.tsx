import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: 'SecondSense: a second look before you pay',
  description: 'Application-layer pre-checkout manipulation-risk and consent layer for PayPal merchant checkout (Sandbox prototype).',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav className="nav"><div className="wrap">
          <Link href="/" className="brand">SecondSense</Link>
          <Link href="/checkout" className="link">Protected checkout</Link><Link href="/dashboard" className="link">Risk studio</Link>
          
          <span className="spacer" /><span className="badge">SANDBOX DEMO</span>
        </div></nav>
        {children}
        <footer><div className="wrap">© SecondSense · Independent checkout-protection prototype. Not affiliated with PayPal. Sandbox payments only.</div></footer>
      </body>
    </html>
  );
}
