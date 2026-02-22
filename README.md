# Pythia — Autonomous Polymarket Trading Agent via MCP

> **The 3 AM headline that moves the market 30%? We catch it. We analyze it. We trade it. You wake up to a freshly printed stack of cash.**

Pythia is an autonomous AI agent that monitors news 24/7, analyzes market impact in real time, and trades on your behalf on [Polymarket](https://polymarket.com) — all running inside ChatGPT through the Model Context Protocol (MCP).

Polymarket is a **$9 billion prediction market** with over **$20 billion in trading volume** and **~700K active monthly users**. The highest-stakes markets on the platform are driven by news events — geopolitics, elections, world conflict, culture, and more. When a headline breaks while you're asleep, the market moves before you can react. Pythia solves that.

---

## How It Works

Pythia maintains a **persistent, real-time data pipeline** directly to Polymarket. Every price, probability shift, and volume spike is live — not stale. That constant connection enables:

- **Accurate AI research** grounded in current market data
- **24/7 autonomous trade management** that doesn't sleep or miss a market move
- **One MCP URL** and you're plugged in

### The Agent Pipeline

When the agent detects a news development, three things happen:

1. **Weighs Significance** — Not every headline moves a market. The LLM determines whether a development actually changes the probability of an outcome, or if it's noise. You can't write a rule for this — it requires reasoning.

2. **Maps Correlations** — News events don't exist in a vacuum. The agent scans every live event on Polymarket and identifies how a development ripples across related markets, because a breakthrough in one event changes the odds of five others.

3. **Models Scenarios** — The agent doesn't just react to what happened. It maps the possible directions a situation could go next and how each scenario would affect pricing across correlated markets.

If the analysis clears the user's **confidence threshold**, it executes automatically. The user sets hard limits on every parameter — categories, position size, confidence threshold. **Nothing executes outside those rails.**

Every trade has a **full audit trail** — what triggered it, correlated events considered, scenario analysis, and why the market was mispriced. Complete transparency.

---

## Architecture

```
User (ChatGPT + MCP Widget)
        │
        ▼
┌─────────────────────────┐
│   MCP Server (TypeScript)│   ← mcp-use SDK, React widget
│   frontend/index.ts      │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   FastAPI Backend        │   ← ChromaDB, Polymarket APIs
│   server/main.py         │
└────────┬────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌──────────────┐
│Research│ │Risk Management│   ← Python AI Agents (OpenAI)
│ Agent  │ │    Agent      │
└────────┘ └──────────────┘
                │
                ▼
        Polymarket CLOB
        (Order Execution)
```

### Components

| Component | Stack | Purpose |
|-----------|-------|---------|
| **MCP Server** | TypeScript, mcp-use SDK | Exposes `get-events` tool to ChatGPT, serves React widget |
| **Widget UI** | React 19, Tailwind CSS | Interactive event explorer, research display, order placement |
| **Backend API** | FastAPI, ChromaDB, Python | Vector search, market data polling, agent orchestration, trading |
| **Research Agent** | Python, OpenAI | Parallel news research across sub-events, synthesis, sentiment analysis |
| **Risk Management Agent** | Python, OpenAI | Batch market analysis, cross-market reconciliation, trading signals |
| **Polymarket Integration** | py-clob-client, Gamma API | Live market data, position tracking, order execution on Polygon |

---

## Project Structure

```
pythia/
├── frontend/                           # MCP Server + React UI
│   ├── index.ts                        # MCP server entry point, tool definitions
│   ├── package.json
│   ├── tsconfig.json
│   └── resources/
│       ├── event-explorer/             # Main widget
│       │   ├── widget.tsx              # Event search, research, risk analysis, ordering
│       │   ├── types.ts               # Zod schemas for all data types
│       │   └── components/
│       │       ├── EventCard.tsx       # Event display with outcomes + prices
│       │       ├── MarketAnalysisCard.tsx  # Risk signals + order UI
│       │       └── EventExplorerSkeleton.tsx
│       ├── monitoring-logs/            # Activity logging widget
│       │   ├── widget.tsx
│       │   └── types.ts
│       └── styles.css                  # Tailwind + custom styling
│
├── server/                             # FastAPI backend
│   ├── main.py                         # API endpoints, ChromaDB, Polymarket integration
│   ├── pyproject.toml
│   └── API_DOCS.md
│
└── agents/                             # Python AI agents
    ├── risk_management_agent/
    │   ├── agent.py                    # Main orchestrator
    │   ├── schemas.py                  # Pydantic models
    │   ├── analyzer.py                 # Batch analysis
    │   ├── reconciler.py               # Cross-market consistency
    │   ├── preprocessor.py             # Input processing
    │   ├── prompts.py                  # LLM prompts
    │   └── config.py
    └── research_agent/                 # Research pipeline
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/search` | POST | Semantic vector search over Polymarket events via ChromaDB |
| `/positions/{user}` | GET | Fetch user's open positions from Polymarket |
| `/order` | POST | Place a market order on Polymarket (BUY/SELL) |
| `/research` | POST | Run research agent — parallel news analysis + synthesis |
| `/risk` | POST | Run risk management agent — trading signals + confidence scores |

---

## User Experience Flow

1. **Search** — User queries events through ChatGPT (e.g., "Bitcoin markets" or "US election"). The MCP tool calls the backend, which performs semantic vector search over all active Polymarket events.

2. **Explore** — The widget displays matching events with live outcome prices, volume, and liquidity. Related events are shown alongside the primary match.

3. **Analyze** — User clicks "Analyze" on an event. Two agents run in parallel:
   - **Research Agent** gathers and synthesizes news across all sub-events
   - **Risk Management Agent** generates trading signals with prediction, confidence, and rationale for each market

4. **Trade** — Each market card shows the agent's signal (BUY/SELL, confidence level, reasoning). The user inputs share amount and executes directly from the widget. Orders go through Polymarket's CLOB on Polygon.

5. **Audit** — Every decision is logged with full reasoning. The user can ask "Why did you make this trade?" and get a complete answer through the ChatGPT conversation.

---

## MCP Integration

Pythia uses the **MCP Apps SDK** (`mcp-use`) to run as a native ChatGPT tool:

- **`useCallTool()`** — Invokes the research pipeline as news breaks
- **`setState()`** — Pushes live updates to the widget even when the user isn't watching
- **`sendFollowUpMessage()`** — Logs every decision back into the conversation for full auditability

This enables **persistent two-way communication** between an autonomous agent and its user.

---

## Setup

### Prerequisites

- Node.js 18+
- Python 3.12+
- A Polymarket wallet (for trading)
- OpenAI API key

### Environment Variables

Create a `.env` file in the `server/` directory:

```bash
OPENAI_API_KEY=sk-...
POLYMARKET_WALLET_ADDRESS=0x...
PRIVATE_KEY=...                    # Required for order execution
```

### Install & Run

**Backend:**

```bash
cd server
pip install -e .    # or: uv pip install -e .
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The backend polls Polymarket's Gamma API every 5 minutes to keep the ChromaDB vector store in sync with all active events.

**Frontend:**

```bash
cd frontend
npm install
npm run dev         # Development server
npm run build       # Production build
npm run deploy      # Deploy to Manufact Cloud
```

### Connect to ChatGPT

Once deployed, add the MCP server URL to ChatGPT. One URL — and you're plugged in.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| MCP Framework | mcp-use (Anthropic MCP Apps SDK) |
| Frontend | React 19, Tailwind CSS 4, Zod, Vite |
| Backend | FastAPI, Uvicorn |
| Vector Search | ChromaDB (persistent) |
| LLM | OpenAI (GPT for research + risk analysis) |
| Market Data | Polymarket Gamma API (events, prices, volume) |
| Position Data | Polymarket Data API |
| Trading | py-clob-client, Polymarket CLOB on Polygon (chain 137) |
| Agents | Custom Python agents with parallel execution |

---

## Design Use Case

Pythia is built for **prediction market traders who can't watch the market 24/7**. The core insight: prediction markets are driven by news, and news breaks at unpredictable times. A human trader who sleeps 8 hours a day is blind for a third of every trading day.

Pythia closes that gap. It gives every trader an autonomous research analyst and execution engine that:

- Never sleeps
- Processes information faster than any human
- Maintains hard risk limits set by the user
- Provides complete transparency on every decision

**30 seconds to install. Connect your wallet, set your risk parameters, activate — and you have an autonomous trading agent that never sleeps.**

---

## Team

Built by **Manufact, Inc.** at the Hackathon.

---

## License

MIT
