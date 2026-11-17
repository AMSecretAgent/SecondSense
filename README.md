## 🧩 Download Chrome Extension

[Download SecondSense Extension](https://github.com/AMSecretAgent/SecondSense/releases/latest)

[demo video link]-(https://www.youtube.com/watch?v=1RLqThTp7mk&t=64s).
### Installation
1. Download `SecondSense-Extension.zip`.
2. Extract the ZIP.
3. Open `chrome://extensions`.
4. Enable Developer mode.
5. Click Load unpacked.
6. Select the extracted folder containing `manifest.json`.
7. Pin SecondSense and test it on the supported demo website.
8. # 🛡️ SecondSense
### Your Second Thought Before You Pay

**An AI-powered payment safety companion designed to help people recognize financial scams before they make a payment.**

Built for the **PayPal AI Hackathon 2026**.

[![Live Demo](https://img.shields.io/badge/Live_Demo-SecondSense-2563EB?style=for-the-badge)](https://second-sense-q6wz.vercel.app)
[![GitHub](https://img.shields.io/badge/GitHub-Source_Code-181717?style=for-the-badge&logo=github)](https://github.com/AMSecretAgent/SecondSense)
![Next.js](https://img.shields.io/badge/Next.js-15-black?style=for-the-badge&logo=nextdotjs)
![FastAPI](https://img.shields.io/badge/FastAPI-Python-009688?style=for-the-badge&logo=fastapi)
![PayPal](https://img.shields.io/badge/PayPal-Sandbox-003087?style=for-the-badge&logo=paypal)

---

## The Problem

**What if a payment is technically legitimate, but the decision to make it was manipulated?**

Imagine receiving a notification claiming you've won a ₹25,000 shopping voucher. To claim it, you're asked to pay a small processing fee.

Or imagine finding premium headphones at an unbelievable discount, accompanied by a countdown timer pressuring you to buy immediately.

These situations exploit human behavior through urgency, excitement, fear, and misplaced trust.

Traditional transaction security can identify certain suspicious financial activities. But payment authorization alone cannot determine whether a user was deceived into making a transaction.

**The critical opportunity is before the payment happens.**

## Introducing SecondSense

SecondSense is a browser-based payment safety companion that evaluates suspicious payment contexts and provides understandable warnings before users proceed.

Rather than focusing exclusively on the transaction, SecondSense considers the circumstances surrounding the user's decision.

Our goal is simple:

> Give people a second thought before they pay.

## Key Features

### 1. Browser-Based Scam Awareness

The SecondSense Chrome extension is designed to introduce safety interventions during potentially suspicious browsing and payment experiences.

The demonstration includes fictional e-commerce scenarios featuring unrealistic discounts, urgency-driven messaging, and suspicious payment requests.

### 2. Contextual Payment Risk Analysis

SecondSense evaluates payment-related context and identifies potential warning signals, including:

- Urgency and time pressure
- Unusual or unrealistic offers
- Suspicious verification fees
- Requests involving questionable payment circumstances
- Social engineering and manipulation indicators

The current backend uses an explainable, heuristic risk-scoring approach. Its scores are indicators for demonstration and are not calibrated fraud probabilities.

### 3. Explainable Risk Warnings

Instead of displaying only a generic fraud alert, SecondSense aims to communicate why a payment situation may be unsafe.

The experience includes risk levels, detected signals, contextual explanations, and user-facing warnings.

### 4. Deliberate Pause Before Payment

High-risk payment scenarios can trigger an additional warning and a mandatory pause before continuing through the protected checkout flow.

This intervention is designed to counteract the urgency that scammers frequently create.

SecondSense supports informed user decisions rather than claiming to guarantee that every fraudulent payment can be blocked.

### 5. PayPal Sandbox Integration

The protected checkout demonstration integrates PayPal Sandbox for testing payment workflows without transferring real money.

The workflow includes:

1. Selecting a demonstration payment scenario.
2. Analyzing its associated risk context.
3. Reviewing the risk assessment.
4. Completing any required warning acknowledgment and pause.
5. Continuing to the PayPal Sandbox checkout when permitted.

**Note:** Sandbox transactions are simulated payment operations, not live financial transactions.

### 6. Personal Payment Safety Dashboard

SecondSense includes a personal safety dashboard concept bringing together:

- Payment safety alerts
- Subscription and renewal reminders
- Financial activity overviews
- Dispute-related guidance

The current dashboard uses illustrative demonstration records rather than synchronized real-world financial account data.

### 7. Investigations Workspace

An AG Grid-powered interface supports structured exploration of fictional payment investigation records.

It demonstrates how risk-related cases could be organized, reviewed, and investigated.

---

## How SecondSense Works

```text
Suspicious payment situation
            |
            v
Browser extension / Protected checkout
            |
            v
Payment context assessment
            |
            v
SecondSense Risk Engine
            |
            v
Risk score + Explainable signals
            |
       +----+----+
       |         |
       v         v
   Lower Risk  Higher Risk
       |         |
       |         v
       |    Contextual Warning
       |         |
       |    Deliberate Pause
       |         |
       |    User Acknowledgment
       |         |
       +----+----+
            |
            v
Eligible PayPal Sandbox Checkout
```

The protected checkout provides the backend-connected risk assessment and payment flow. Browser-extension behavior depends on the supported page and its detection logic.

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | Next.js 15, React, TypeScript |
| Styling | Tailwind CSS |
| Backend | Python, FastAPI, Uvicorn |
| Risk Assessment | Explainable heuristic scoring |
| Payment Integration | PayPal REST APIs, PayPal Sandbox |
| Browser Integration | Chrome Extension |
| Investigation Interface | AG Grid |
| Frontend Hosting | Vercel |
| Backend Hosting | Railway |
| Version Control | Git, GitHub |

## Live Application

**Website:** https://second-sense-q6wz.vercel.app

| Page | Purpose |
|---|---|
| `/` | Product introduction and landing page |
| `/checkout` | Risk analysis and protected PayPal Sandbox checkout |
| `/dashboard` | Personal payment safety dashboard |
| `/investigations` | Investigation records and case exploration |

**Backend:** https://secondsense-production.up.railway.app

**Configuration endpoint:** https://secondsense-production.up.railway.app/api/config

## Demo Scenarios

SecondSense can be demonstrated using controlled, fictional websites designed to reproduce common online scam patterns.

### Scenario A: Unrealistic Shopping Discount

A fictional online store advertises heavily discounted headphones and uses time-sensitive promotional messaging.

**Demonstration objective:** Evaluate how SecondSense responds to suspicious shopping and payment contexts.

### Scenario B: Spin-to-Win Prize Claim

A fictional rewards page announces a ₹25,000 voucher but introduces a ₹49 handling fee to claim the prize.

**Demonstration objective:** Illustrate how small verification fees and prize-related urgency can be used in phishing-style schemes.

These websites are educational simulations. They do not process real payments or collect actual card credentials.

## Getting Started

### Prerequisites

- Node.js and npm
- Python
- Git
- A modern Chromium-based browser
- PayPal Developer Sandbox credentials for payment testing

### 1. Clone the Repository

```bash
git clone https://github.com/AMSecretAgent/SecondSense.git
cd SecondSense
```

### 2. Start the Frontend

```bash
cd frontend
npm install
```

Create a `frontend/.env.local` file:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Start the development server:

```bash
npm run dev
```

Open http://localhost:3000.

### 3. Configure the Backend

Open a separate terminal:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment.

**Windows:**

```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux:**

```bash
source .venv/bin/activate
```

Install the backend dependencies using the dependency manifest included in the repository.

Configure the required backend environment variables, including PayPal Sandbox credentials and allowed frontend origins.

For example:

```env
ALLOWED_ORIGINS=http://localhost:3000
PAYPAL_ENVIRONMENT=sandbox
PAYPAL_CLIENT_ID=your_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_sandbox_client_secret
```

Never commit real credentials or secret environment files.

Start the FastAPI application using the backend entry point:

```bash
uvicorn main:app --reload --port 8000
```

The API should be accessible at http://localhost:8000.

**Important:** Check the backend's dependency file and configuration module for the complete installation and environment requirements before local deployment.

### 4. Chrome Extension

To install a packaged, unpacked Chrome extension for local testing:

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked**.
4. Choose the extension directory containing `manifest.json`.
5. Enable the extension's site permissions for the demonstration website.
6. Refresh the test page.

Extension behavior and supported websites should be verified using the included demonstration scenarios.

## Security and Privacy Considerations

SecondSense is designed around user awareness, explainability, and safer payment decisions.

Important implementation principles include:

- Payment credentials must not be exposed in client-side code.
- PayPal secret credentials remain on the backend.
- Payment demonstrations use PayPal Sandbox.
- Fictional scam pages must not collect real payment credentials.
- Risk assessments should communicate uncertainty and limitations.
- User-facing warnings should explain detected risk indicators.
- The system should not be presented as a replacement for payment-provider security controls.

## Current Scope and Limitations

SecondSense is a hackathon prototype.

The current implementation demonstrates browser-based payment safety concepts, contextual risk assessment, explainable warnings, a protected checkout workflow, and supporting financial safety interfaces.

The risk engine uses heuristic scoring rather than a validated, production-grade fraud detection model.

Some interfaces use fictional records, and demonstration pages simulate suspicious behavior without processing real transactions.

The browser extension is intended to provide additional user-facing protection, but detection and intervention should not be assumed to work on every website or payment provider.

## Future Roadmap

Potential future improvements include:

- Machine-learning-based fraud risk models trained on appropriately sourced data
- Broader browser compatibility and payment-page coverage
- More sophisticated social engineering and behavioral signal detection
- Multilingual, accessible risk explanations
- Privacy-preserving transaction context analysis
- User-controlled payment safety preferences
- Expanded dispute assistance workflows
- Production-grade authentication and secure financial integrations
- Real-world usability testing and model evaluation

## Why SecondSense?

Fraud prevention isn't only about identifying malicious transactions.

It is also about understanding how people are persuaded to make risky decisions.

A user may willingly authorize a payment while being manipulated by a false emergency, an unrealistic offer, or a deceptive prize.

SecondSense explores an additional layer of financial protection: **contextual awareness at the moment of decision.**

## Hackathon

**Project:** SecondSense  
**Event:** PayPal AI Hackathon 2026  
**Developer:** Akansha Mishra  
**Category:** FinTech / Payment Safety / Fraud Prevention

## Disclaimer

SecondSense is an experimental hackathon prototype developed for educational and demonstration purposes.

It does not guarantee fraud detection, provide financial advice, or replace the fraud prevention systems of payment providers and financial institutions.

All scam simulations and fictional financial records are used solely for demonstration.

---

### SecondSense — Your Second Thought Before You Pay.

*Because the safest payment might be the one you reconsider.*
