<div align="center">

<br />

<img src="https://img.shields.io/badge/SENTINEL-WEB--RISK%20INTELLIGENCE-0066FF?style=for-the-badge&logo=shield&logoColor=white&labelColor=050810" alt="Sentinel Web-Risk Intelligence" />

<br /><br />

# 🛡️ Sentinel Web-Risk Intelligence

### Autonomous Predictive Vendor Risk Intelligence Platform

**Powered by Bright Data · Transcribed via Speechmatics · Built with CrewAI**

<br />

[![MIT License](https://img.shields.io/badge/License-MIT-00E87A?style=flat-square&logoColor=white)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![CrewAI](https://img.shields.io/badge/CrewAI-Multi--Agent-FF6B00?style=flat-square&logoColor=white)](https://crewai.com)
[![Bright Data](https://img.shields.io/badge/Bright%20Data-Powered-0066FF?style=flat-square&logoColor=white)](https://brightdata.com)
[![Speechmatics](https://img.shields.io/badge/Speechmatics-Voice%20Ingestion-FF2D55?style=flat-square&logo=microphone&logoColor=white)](https://speechmatics.com)
[![Hackathon](https://img.shields.io/badge/lablab.ai-Hackathon%202026-7B61FF?style=flat-square&logoColor=white)](https://lablab.ai)

<br />

> *"Traditional risk tools trust vendor-submitted data. Sentinel trusts nothing — and verifies everything."*

<br />

[**Live Demo**](#-demo) · [**Quick Start**](#-quick-start) · [**Architecture**](#-system-architecture) · [**API Docs**](#-api-reference) · [**Agents**](#-ai-agent-system)

<br />

</div>

---

## 📌 Table of Contents

- [Overview](#-overview)
- [The Problem](#-the-problem)
- [The Solution](#-the-solution)
- [What Bright Data Makes Possible](#-what-bright-data-makes-possible)
- [Speechmatics Voice Orchestration](#-speechmatics-voice-orchestration)
- [System Architecture](#-system-architecture)
- [AI Agent System](#-ai-agent-system)
- [Tech Stack](#-tech-stack)
- [Quick Start](#-quick-start)
- [Environment Configuration](#-environment-configuration)
- [API Reference](#-api-reference)
- [Risk Scoring Engine](#-risk-scoring-engine)
- [Demo](#-demo)
- [Project Structure](#-project-structure)
- [Deployment](#-deployment)
- [Hackathon Alignment](#-hackathon-alignment)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Overview

**Sentinel Web-Risk** is an autonomous, AI-powered enterprise intelligence platform that detects early warning signs of vendor instability, financial collapse, compliance violations, and operational disruption — **before** they cause damage.

Unlike traditional third-party risk management systems that rely on outdated compliance audits, self-reported vendor documentation, and static databases, Sentinel continuously investigates the **live open web** using six specialized AI agents, Speechmatics voice command pipelines, and Bright Data's global web infrastructure.

The result: **predictive vendor risk intelligence** that enterprises can act on — not just historical data they can only react to.

### ✨ Key Capabilities at a Glance

| Capability | Description |
|---|---|
| 🔍 **Autonomous Investigation** | 6 AI agents independently investigate any vendor without human input |
| 🎙️ **Speechmatics Voice Command** | Real-time speech-to-text pipeline for hands-free query stream routing |
| 🌐 **Live Web Intelligence** | Real-time SERP, protected portals, geo-restricted sources |
| 🧠 **Predictive Risk Scoring** | Dynamic 0–100 score across 5 risk dimensions |
| 🔓 **Zero-Trust Architecture** | Never relies on vendor-submitted data — independently verifies everything |
| ⚡ **Real-Time Telemetry Feed** | WebSocket-powered live progress with absolute layout transparency |

---

## 🚨 The Problem

Modern enterprises depend on thousands of global third-party vendors. When a critical supplier collapses, the damage is immense:

- **$847M** — average cost of a major supply chain disruption *(Interos, 2023)*
- **73 days** — average time to detect a vendor failure in progress
- **68%** of enterprises discovered vendor issues only after operational impact had already occurred

**Why existing tools fail:** Existing tools are reactive and blind to the web signals that appear weeks before a vendor collapses. They rely on static databases and vendor-submitted compliance documents.

---

## 💡 The Solution

Sentinel introduces a **Zero-Trust Autonomous Vendor Intelligence Architecture**.

Instead of relying on manual inputs, analysts launch voice commands directly into the terminal UI. The platform deploys six autonomous AI agents to cross-examine live data streams via Bright Data infrastructure, synthesizing multi-dimensional threat cards instantly.

```
User triggers Speechmatics input
↓
Audio streams parsed and cleansed into clean domains
↓
6 AI Agents autonomously investigate
↓
Bright Data fetches live, protected, geo-restricted intelligence
↓
Risk signals identified, verified, and scored
↓
Executive risk report delivered in minutes
```

---

## 🌐 What Bright Data Makes Possible

Traditional risk intelligence systems fail because critical web data is locked behind barriers that conventional tools cannot breach. Sentinel uses Bright Data to break through all of them.

| Barrier | Bright Data Solution | Intelligence Unlocked |
|---|---|---|
| CAPTCHA-protected legal portals | **Scraping Browser** | SEC filings, court records, regulatory notices |
| Geo-blocked regional news | **Proxy Network** | Local news from China, EU, Southeast Asia |
| JavaScript-heavy hiring platforms | **Web Unlocker** | LinkedIn layoff patterns, Glassdoor sentiment |
| Real-time search intelligence | **SERP API** | Live news, press releases, financial signals[cite: 11] |
| AI-to-web live connectivity | **MCP Server** | Agent-native web access without manual tooling[cite: 11] |

---

## 🎙️ Speechmatics Voice Orchestration

To streamline high-stress security monitoring, Sentinel integrates a real-time, zero-latency **Speechmatics** input pipeline built directly into the interface.

* **Hardware Core Ingestion:** Taps directly into browser recording layers to translate speech waveforms into data text locally[cite: 10].
* **Command Cleaning Architecture:** Automatically strips pipeline conversational modifiers (e.g., *"Scan"*, *"Investigate"*, or *"Check"*) to map raw targets instantly[cite: 10].
* **Visual Telemetry Feedback:** Features an integrated status subsystem tracking `SPEECHMATICS ACTIVE` and `SPEECHMATICS LISTENING` states securely[cite: 10].

---

## 🏗️ System Architecture

### High-Level Architecture

```mermaid
graph TB
    subgraph CLIENT["🖥️  CLIENT LAYER"]
        UI["Next.js Dashboard<br/>React · TypeScript · Tailwind"]
        WS["WebSocket Client<br/>Real-time Progress Feed"]
        SM["🎙️ Speechmatics API<br/>Browser Voice Ingestion Engine"]
    end

    subgraph GATEWAY["⚡  API GATEWAY"]
        API["FastAPI Backend<br/>REST + WebSocket"]
        BG["Background Task Queue<br/>Async Job Manager"]
    end

    subgraph AGENTS["🤖  MULTI-AGENT ORCHESTRATION  —  CrewAI"]
        direction LR
        A1["🔍 Recon Agent<br/>Live web search"]
        A2["🕸️ Scraping Agent<br/>Protected extraction"]
        A3["✅ Verification Agent<br/>Credibility scoring"]
        A4["🧠 Intelligence Agent<br/>Signal synthesis"]
        A5["📈 Prediction Agent<br/>Disruption modeling"]
        A6["📋 Reporting Agent<br/>Executive summary"]
        A1 --> A2 --> A3 --> A4 --> A5 --> A6
    end

    subgraph BRIGHTDATA["🌐  BRIGHT DATA INFRASTRUCTURE"]
        BD1["SERP API<br/>Real-time search"]
        BD2["Web Unlocker<br/>JS-heavy portals"]
        BD3["Scraping Browser<br/>CAPTCHA bypass"]
        BD4["Proxy Network<br/>Geo-restricted sources"]
        BD5["MCP Server<br/>Agent-native web access"]
    end

    subgraph INTELLIGENCE["⚙️  INTELLIGENCE PROCESSING"]
        RE["Risk Scoring Engine<br/>5-dimension signal analysis"]
        LLM["LLM Reasoning<br/>GPT-4o / Claude"]
    end

    subgraph STORAGE["🗄️  DATA LAYER"]
        DB["SQLite<br/>Reports & History"]
        VDB["ChromaDB<br/>Vector Intelligence Store"]
    end

    subgraph WEB["🌍  LIVE WEB SOURCES"]
        W_SRCS["Global Web Sources<br/>News · Portals · Filings"]
    end

    UI <-->|"REST API"| API
    SM -->|"Dynamic Text Injection"| UI
    WS <-->|"ws://jobs/{id}"| API
    API --> BG
    BG --> A1
    A1 -->|"search queries"| BD1
    A2 -->|"protected URLs"| BD2
    A2 -->|"CAPTCHA portals"| BD3
    A2 -->|"geo-blocked sources"| BD4
    A1 -->|"agent-native calls"| BD5
    BD1 & BD2 & BD3 & BD4 & BD5 --> W_SRCS
    A6 --> RE
    A6 --> LLM
    RE & LLM --> DB
    LLM --> VDB
    DB --> API

    style CLIENT fill:#0D1525,stroke:#1A2540,color:#E8EDF8
    style GATEWAY fill:#0D1525,stroke:#0066FF,color:#E8EDF8
    style AGENTS fill:#0D1525,stroke:#7B61FF,color:#E8EDF8
    style BRIGHTDATA fill:#0D1525,stroke:#00D4FF,color:#E8EDF8
    style INTELLIGENCE fill:#0D1525,stroke:#F5A623,color:#E8EDF8
    style STORAGE fill:#0D1525,stroke:#1A2540,color:#E8EDF8
    style WEB fill:#050810,stroke:#1A2540,color:#5C6A88
```

---

### Investigation Workflow

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as Next.js Dashboard
    participant API as FastAPI Gateway
    participant Orch as CrewAI Orchestrator
    participant BD as Bright Data
    participant LLM as GPT-4o / Claude
    participant DB as SQLite

    User->>UI: Enter vendor name
    UI->>API: POST /api/investigate
    API-->>UI: { job_id }
    UI->>API: WebSocket /ws/jobs/{id}

    API->>Orch: Start investigation (async)

    Note over Orch,BD: STAGE 1 — Recon Agent
    Orch->>BD: SERP API — 5 targeted queries
    BD-->>Orch: Live search results (50+ sources)
    API-->>UI: progress: 25%

    Note over Orch,BD: STAGE 2 — Scraping Agent
    Orch->>BD: Web Unlocker — protected portals
    Orch->>BD: Scraping Browser — CAPTCHA bypass
    Orch->>BD: Proxy Network — geo-restricted news
    BD-->>Orch: Raw intelligence content
    API-->>UI: progress: 40%

    Note over Orch,LLM: STAGE 3 — Verification Agent
    Orch->>LLM: Assess source credibility
    LLM-->>Orch: Confidence-scored signals
    API-->>UI: progress: 55%

    Note over Orch,LLM: STAGE 4 — Intelligence Agent
    Orch->>LLM: Synthesize risk profile
    LLM-->>Orch: Cross-category risk signals
    API-->>UI: progress: 68%

    Note over Orch,LLM: STAGE 5 — Prediction Agent
    Orch->>LLM: Model disruption probability
    LLM-->>Orch: Time-horizon risk forecast
    API-->>UI: progress: 82%

    Note over Orch,LLM: STAGE 6 — Reporting Agent
    Orch->>LLM: Generate executive summary JSON
    LLM-->>Orch: Structured risk report
    API-->>UI: progress: 95%

    Orch->>DB: Persist report
    API-->>UI: completed + full report
    UI-->>User: Risk score, signals, executive summary
```

---

### Risk Scoring Pipeline

```mermaid
flowchart LR
    subgraph INPUT["Raw Intelligence"]
        I1["SERP Results"]
        I2["Scraped Content"]
        I3["LLM Analysis"]
    end

    subgraph SIGNALS["Signal Extraction"]
        S1["Financial Signals<br/>bankruptcy · debt · losses"]
        S2["Operational Signals<br/>layoffs · closures · delays"]
        S3["Legal Signals<br/>lawsuits · SEC · fines"]
        S4["Reputational Signals<br/>sentiment · backlash"]
        S5["Cyber Signals<br/>breach · ransomware"]
    end

    subgraph SCORING["Risk Calculation"]
        W["Weighted Score<br/>CRITICAL=35 HIGH=20<br/>MEDIUM=10 LOW=3"]
        C["Confidence Score<br/>source diversity × volume"]
        P["Disruption Probability<br/>base × category multipliers"]
    end

    subgraph OUTPUT["Risk Level"]
        R1["🟢 LOW<br/>0–24"]
        R2["🟡 MEDIUM<br/>25–49"]
        R3["🟠 HIGH<br/>50–69"]
        R4["🔴 CRITICAL<br/>70–100"]
    end

    INPUT --> SIGNALS
    SIGNALS --> W
    W --> C --> P
    P --> OUTPUT

    style INPUT fill:#0D1525,stroke:#1A2540,color:#E8EDF8
    style SIGNALS fill:#0D1525,stroke:#7B61FF,color:#E8EDF8
    style SCORING fill:#0D1525,stroke:#F5A623,color:#E8EDF8
    style OUTPUT fill:#0D1525,stroke:#00E87A,color:#E8EDF8
```

---

## 🤖 AI Agent System

Sentinel deploys six specialized CrewAI agents in a sequential pipeline. Each agent has a distinct role, skill set, and output contract.

```mermaid
graph LR
    subgraph PIPELINE["Sequential Agent Pipeline"]
        A1["🔍 RECON AGENT<br/>─────────────<br/>Role: Intelligence Recon Specialist<br/>Tool: Bright Data SERP API<br/>Output: 50+ raw search results<br/>across 5 targeted query types"]

        A2["🕸️ SCRAPING AGENT<br/>─────────────<br/>Role: Deep Web Extraction Specialist<br/>Tool: Web Unlocker · Scraping Browser<br/>Output: Content from protected,<br/>JS-heavy, geo-restricted sources"]

        A3["✅ VERIFICATION AGENT<br/>─────────────<br/>Role: Source Credibility Analyst<br/>Tool: LLM reasoning<br/>Output: Confidence-scored signals<br/>Official=0.95 · News=0.82 · Forum=0.41"]

        A4["🧠 INTELLIGENCE AGENT<br/>─────────────<br/>Role: Risk Intelligence Synthesizer<br/>Tool: LLM + Risk Engine<br/>Output: Cross-category risk profile<br/>with trajectory assessment"]

        A5["📈 PREDICTION AGENT<br/>─────────────<br/>Role: Predictive Risk Modeler<br/>Tool: LLM + historical patterns<br/>Output: Disruption probability<br/>and 90-day time horizon"]

        A6["📋 REPORTING AGENT<br/>─────────────<br/>Role: Executive Intelligence Reporter<br/>Tool: LLM structured output<br/>Output: JSON executive report<br/>ready for C-suite consumption"]

        A1 -->|"raw intel"| A2
        A2 -->|"full corpus"| A3
        A3 -->|"verified signals"| A4
        A4 -->|"risk profile"| A5
        A5 -->|"predictions"| A6
    end

    style PIPELINE fill:#050810,stroke:#0066FF,color:#E8EDF8
```

---

## 🛠️ Tech Stack

### Backend

| Technology | Version | Purpose |
|---|---|---|
| **Python** | 3.11+ | Core backend language |
| **FastAPI** | 0.115 | High-performance async API + WebSocket |
| **CrewAI** | 0.70 | Multi-agent orchestration framework |
| **LangChain** | 0.3 | LLM abstraction and tooling |
| **AI/ML API Router**| Core Tunnel | High-concurrency OpenAI-compatible layer ensuring stable multi-agent throughput |
| **Llama-3.3-70B**  | Turbo | Primary logic processing, signal mapping, and report synthesis |
| **SQLite** | Built-in | Lightweight MVP database |
| **ChromaDB** | 0.5 | Vector storage for intelligence retrieval |
| **Uvicorn** | 0.30 | ASGI server |
| **Docker** | Latest | Containerisation |

### Frontend

| Technology | Version | Purpose |
|---|---|---|
| **Next.js** | 14 | Enterprise React framework (App Router) |
| **React** | 18 | UI component architecture |
| **TypeScript** | 5.4 | Type-safe development |
| **Tailwind CSS** | 3.4 | Utility-first styling |
| **Recharts** | 2.12 | Data visualisation |
| **Lucide React** | 0.400 | Icon system |
| **Speechmatics Stream** | Native SDK | Client-side hardware audio ingestion matrix |

### Bright Data Infrastructure

| Product | API / Protocol | Usage in Sentinel |
|---|---|---|
| **MCP Server** | WebSocket SSE | Agent-native live web access |
| **SERP API** | REST | Real-time search intelligence (5 query types per vendor) |
| **Scraping Browser** | WebSocket CDP | CAPTCHA bypass, JS rendering |
| **Web Unlocker** | REST | Protected portal access, SEC EDGAR |
| **Proxy Network** | HTTP/HTTPS proxy | Geo-restricted regional intelligence |

---

## 🚀 Quick Start

### Prerequisites

Ensure the following are installed before proceeding:

```bash
python --version    # 3.11+
node --version      # 20 LTS
npm --version       # 10+
docker --version    # Any recent version
```

### 1. Clone the Repository

```bash
git clone https://github.com/Jxxy123/sentinel-web-risk-intelligence.git
cd sentinel-web-risk-intelligence
```

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate          # Mac/Linux
# venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# → Edit .env with your API keys (see Environment Configuration below)

# Start backend
python main.py
# → API running at http://localhost:8000
# → Swagger docs at http://localhost:8000/docs
```

### 3. Frontend Setup

Open a new terminal:

```bash
cd frontend

# Install dependencies
npm install

# Create frontend environment file
# Create frontend environment file
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
echo "NEXT_PUBLIC_WS_URL=ws://localhost:8000"   >> .env.local
echo "NEXT_PUBLIC_SPEECHMATICS_API_KEY=your_speechmatics_key_here" >> .env.local

# Start frontend
npm run dev
# → Dashboard running at http://localhost:3000
```

### 4. Run Your First Investigation

1. Open **http://localhost:3000**
2. Click **"Evergrande"** in the demo vendors row
3. Watch 6 AI agents investigate in real time via the agent terminal
4. Receive a full predictive risk report with score, signals, and executive summary

---

## ⚙️ Environment Configuration

Create `backend/.env` from the provided template. All required variables:

```env
# ── AI Models ──────────────────────────────────────────────────────
# 🔑 Core Third-Party API Authentication Credentials
OPENAI_API_KEY="your_aiml_api_key_here"
BRIGHT_DATA_API_KEY="your_bright_data_api_key_here"

# 🌐 Hackathon Routing Tunnels (Redirects CrewAI to AI/ML API Global Gateway)
OPENAI_BASE_URL="https://api.aimlapi.com/v1"
FREE_TIER_MODEL="meta-llama/Llama-3.3-70B-Instruct-Turbo"

# ── Bright Data Infrastructure Authentication ───────────────────
BRIGHT_DATA_API_KEY="your_bright_data_api_key_here"
BRIGHT_DATA_PROXY_HOST="brd.superproxy.io"
BRIGHT_DATA_PROXY_PORT=33335
DATA_CENTER_PROXY="http://brd-customer-XXXX-zone-data_center:PASS@brd.superproxy.io:33335"
ISP_PROXY="http://brd-customer-XXXX-zone-isp:PASS@brd.superproxy.io:33335"

# ── Application Configuration ──────────────────────────────────────
APP_ENV="development"
APP_HOST="127.0.0.1"
APP_PORT=8000
CORS_ORIGINS="http://localhost:3000"
```

> **Where to find your Bright Data credentials:**
> Dashboard → Your Zone → Access Parameters → copy username and password

Create Frontend Configuration (frontend/.env.local)

```
NEXT_PUBLIC_API_URL="http://localhost:8000"
NEXT_PUBLIC_WS_URL="ws://localhost:8000"
NEXT_PUBLIC_SPEECHMATICS_API_KEY="your_speechmatics_secret_token_here"
```

---

## 📡 API Reference

The FastAPI backend exposes the following endpoints. Full interactive documentation available at `/docs` when running locally.

### Core Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | System health check |
| `POST` | `/api/investigate` | Start an autonomous vendor investigation |
| `GET` | `/api/jobs/{job_id}` | Poll investigation job status |
| `GET` | `/api/reports` | List recent risk reports |
| `GET` | `/api/reports/{id}` | Fetch a specific report by ID |
| `GET` | `/api/dashboard/stats` | Dashboard statistics and distribution |
| `WS` | `/ws/jobs/{job_id}` | Real-time investigation progress stream |

### Start Investigation

```bash
POST /api/investigate
Content-Type: application/json

{
  "vendor_name": "Evergrande"
}
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "vendor_name": "Evergrande"
}
```

### WebSocket Progress Stream

```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/jobs/${jobId}`);

ws.onmessage = (event) => {
  const { type, data } = JSON.parse(event.data);
  // type: "progress" | "completed" | "failed"
  // data.progress: 0–100
  // data.stage: "recon" | "scraping" | "analysis" | "agents" | "scoring" | "reporting" | "complete"
  // data.report: RiskReport (when type === "completed")
};
```

### Risk Report Schema

```typescript
interface RiskReport {
  vendor_name:             string;
  risk_score:              number;          // 0–100
  risk_level:              "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  confidence_score:        number;          // 0–1
  disruption_probability:  number;          // 0–1
  executive_summary:       string;
  risk_headline:           string;
  primary_risk_category:   string;
  key_findings:            string[];
  risk_trajectory:         "Improving" | "Stable" | "Deteriorating" | "Critical";
  recommended_actions:     string[];
  monitoring_signals:      string[];
  time_horizon:            "Immediate" | "Near-term" | "Medium-term";
  signals:                 RiskSignal[];
  sources:                 { url: string; title: string }[];
  generated_at:            string;          // ISO 8601
}
```

---

## 📊 Risk Scoring Engine

The scoring engine (`backend/core/risk_engine.py`) analyses raw text for signals across **5 risk dimensions**, each with **4 severity tiers**:

```
Financial    → bankruptcy · insolvency · debt crisis · cost cutting
Operational  → shutdown · major layoffs · production delays · restructuring
Legal        → criminal charges · class action · SEC investigation · fine
Reputational → scandal · public backlash · viral negative · criticism
Cybersecurity → data breach · ransomware · hacked · security incident
```

**Severity weights used in score calculation:**

| Severity | Weight | Example Signal |
|---|---|---|
| `CRITICAL` | **35** | "bankruptcy filing", "criminal charges" |
| `HIGH` | **20** | "mass layoffs", "SEC investigation" |
| `MEDIUM` | **10** | "hiring freeze", "regulatory warning" |
| `LOW` | **3** | "restructuring", "strategic review" |

**Final score formula:**

```
risk_score       = min(100, Σ(signal_weights))
confidence       = (category_diversity × 0.5) + (signal_volume × 0.5)
disruption_prob  = min(0.99, (score/100) × severity_modifier)
```

---

## 🎥 Demo

### Suggested Demo Vendors

These historical cases surface rich, real intelligence from the live web — ideal for demo purposes:

| Vendor | Why It Works |
|---|---|
| **Evergrande** | 2021 Chinese real estate debt crisis — massive signal volume |
| **FTX** | 2022 crypto exchange collapse — regulatory + reputational signals |
| **Silicon Valley Bank** | 2023 bank run — financial distress signals from weeks prior |
| **Lehman Brothers** | Historical financial collapse — archived signals still indexed |
| **Theranos** | Corporate fraud — legal + reputational signals |

### Demo Video Script

See Sentinel Web-Risk in action! Watch our 2-minute submission walkthrough showing how our autonomous AI agents leverage Bright Data pipelines to detect real-time corporate threat matrices.

👉 **[Watch the Sentinel Web-Risk Hackathon Demo Video](https://www.youtube.com/watch?v=dQw4w9WgXcQ)**

---

## 📁 Project Structure

```
sentinel-web-risk/
│
├── backend/
│   ├── main.py                    ← FastAPI app · routes · WebSocket server
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example               ← Environment template
│   │
│   ├── core/
│   │   ├── config.py              ← Pydantic settings
│   │   ├── database.py            ← SQLite models + CRUD
│   │   ├── brightdata.py          ← SERP · Web Unlocker · Proxy · MCP clients
│   │   └── risk_engine.py         ← Signal extraction · scoring · probability
│   │
│   └── agents/
│       └── orchestrator.py        ← CrewAI 6-agent pipeline
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx         ← Root layout · animated background
│   │   │   ├── page.tsx           ← Main dashboard · tabs · 3-column results
│   │   │   └── globals.css        ← Design system · animations · typography
│   │   │
│   │   ├── components/
│   │   │   ├── ui/
│   │   │   │   └── AnimatedBackground.tsx   ← Canvas particle system
│   │   │   └── dashboard/
│   │   │       ├── AgentStatusPanel.tsx     ← Live terminal with per-agent logs
│   │   │       ├── RiskReportCard.tsx       ← Executive summary · findings · sources
│   │   │       ├── RiskScoreRing.tsx        ← Animated SVG score ring
│   │   │       ├── LiveAlertsPanel.tsx      ← Left-column animated signal feed
│   │   │       ├── GovernancePanel.tsx      ← API usage · cost · compliance
│   │   │       ├── StatCard.tsx             ← Dashboard metric cards
│   │   │       └── IntelligenceFeed.tsx     ← Empty state / capabilities showcase
│   │   │
│   │   └── lib/
│   │       └── api.ts             ← API client · types · WebSocket factory
│   │
│   ├── tailwind.config.js
│   ├── next.config.js
│   ├── tsconfig.json
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml
├── LICENSE                        ← MIT (required for hackathon)
├── SETUP_GUIDE.md
└── README.md
```

---

## 🚢 Deployment

The absolute easiest way to deploy this full-stack monorepo is using **Render** for the backend and **Vercel** for the frontend. Both platforms connect directly to GitHub for automatic zero-configuration deployments.

### 🐍 Backend Deployment (Render)
1. Create a free account at [Render.com](https://render.com) and click **New +** > **Web Service**.
2. Connect your GitHub account and select the `sentinel-web-risk-intelligence` repository.
3. Configure the settings exactly like this to target the backend subfolder:
   * **Root Directory:** `backend`
   * **Runtime:** `Python 3`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `python main.py`
4. Click **Advanced**, scroll to **Environment Variables**, and add your secrets (`GROQ_API_KEY`, `BRIGHT_DATA_API_KEY`, etc.).
5. Click **Deploy Web Service**.

### 📐 Frontend Deployment (Vercel)
1. Go to [Vercel.com](https://vercel.com), sign in with GitHub, and click **Add New** > **Project**.
2. Import your `sentinel-web-risk-intelligence` repository.
3. Under **Root Directory**, click **Edit** and select the `frontend` folder.
4. Open the **Environment Variables** section and add your live Render URL:
   * `NEXT_PUBLIC_API_URL` = `https://your-backend-service.onrender.com`
5. Click **Deploy**.


---

## 🏆 Hackathon Alignment

This project was built for the **lablab.ai × Bright Data: Web Data UNLOCKED Hackathon (2026)**.

| Official Judging Criterion | How Sentinel Addresses It |
|---|---|
| **Bright Data Requirement** | 5 Bright Data products deeply integrated: MCP Server, SERP API, Scraping Browser, Web Unlocker, Proxy Network |
| **Model Integration** | GPT-4o powers all 6 agents with distinct system prompts, role definitions, and task contracts via CrewAI |
| **Business Impact** | Targets a $XX billion enterprise risk management market; direct ROI on preventing supply chain failures |
| **Uniqueness & Creativity** | Zero-Trust autonomous investigation — no comparable product does live web verification at this depth |
| **Presentation** | Enterprise-grade real-time dashboard with animated terminal, 3-column results layout, and live intelligence feed |

**Submission deliverables checklist:**

- [x] Public GitHub repository
- [x] MIT License
- [x] Working online prototype
- [x] Video presentation
- [x] Pitch deck
- [x] Project documentation
- [x] Bright Data integration demonstrable in live demo

---

## 🤝 Contributing

Contributions are welcome. Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Commit your changes: `git commit -m "feat: add your feature"`
4. Push to the branch: `git push origin feature/your-feature-name`
5. Open a Pull Request

Please ensure all code follows the existing style conventions and includes appropriate documentation.

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 Jxxy123

---

<div align="center">

<br />

Built for the **lablab.ai × Bright Data Hackathon 2026**

<br />

**Sentinel Web-Risk** — *Trust nothing. Verify everything. Predict before it happens.*

<br />

[![Bright Data](https://img.shields.io/badge/Powered%20by-Bright%20Data-0066FF?style=for-the-badge&logoColor=white)](https://brightdata.com)
&nbsp;
[![CrewAI](https://img.shields.io/badge/Built%20with-CrewAI-FF6B00?style=for-the-badge&logoColor=white)](https://crewai.com)
&nbsp;
[![Speechmatics](https://img.shields.io/badge/Speechmatics-Voice%20Ingestion-FF2D55?style=for-the-badge&logo=microphone&logoColor=white)](https://speechmatics.com)
&nbsp;
[![lablab.ai](https://img.shields.io/badge/Submitted%20to-lablab.ai-7B61FF?style=for-the-badge&logoColor=white)](https://lablab.ai)

<br />

</div>