# Risk Management Agent — Implementation Plan

## Context

The research agent is working and producing correct results. The next piece of the pipeline is a **risk management agent** that takes cleaned research output + a list of prediction markets (~20 markets per event), and produces **Buy/Sell/Hold trading signals** for each market. This agent sits between the research phase and trade execution — its job is to identify mispricing across markets under a single event.

---

## Architecture

**Two-stage parallel pipeline** (no web search, pure reasoning):

1. **Stage 1 — Parallel Batch Analysis**: Split ~20 markets into batches of 5, fire off 4 concurrent LLM calls. Each batch gets the full research context + its 5 markets. Markets within a batch can inform each other.
2. **Stage 2 — Reconciliation**: A lightweight LLM call reviews all signals together for cross-batch consistency (e.g., ensuring Feb 24 isn't BUY when Feb 22 and Feb 23 are both SELL).

This gives ~4x speedup over a single call while maintaining signal coherence.

```
agents/
├── risk_management_agent/       # NEW
│   ├── __init__.py              # Public exports
│   ├── agent.py                 # RiskManagementAgent orchestrator (parallel batches)
│   ├── analyzer.py              # Batch LLM call with retry + fallback
│   ├── reconciler.py            # Cross-batch consistency check
│   ├── config.py                # Frozen dataclass config
│   ├── prompts.py               # Prompt templates (analysis + reconciliation)
│   └── schemas.py               # Pydantic input/output models
├── api.py                       # MODIFY — add /risk endpoint
├── run_risk.py                  # NEW — CLI entry point
└── (existing files unchanged)
```

---

## Files to Create

### 1. `risk_management_agent/schemas.py` — Input/Output Models

**Input (`RiskAnalysisInput`):**
- `research_summary: str` — cleaned summary from research agent
- `key_findings: list[str]` — key findings (min 1)
- `sentiment: SentimentRating` — enum: very_bearish / bearish / neutral / bullish / very_bullish
- `main_event: MainEventInfo` — title + optional description
- `markets: list[Market]` — each has id, title, optional current_price (0.0–1.0), optional description

**Output (`RiskAnalysisOutput`):**
- `event_title: str`
- `signals: list[MarketSignal]` — one per market
- `overall_analysis: str` — 2-4 paragraph summary
- `timestamp: str` — ISO 8601
- `disclaimer: str`

**`MarketSignal`:**
- `market_id`, `market_title`
- `signal: TradingSignal` — enum: buy / sell / hold
- `confidence: ConfidenceLevel` — enum: high / medium / low
- `rationale: str` — 2-4 sentences grounded in research findings

### 2. `risk_management_agent/config.py` — Configuration

Frozen dataclass `RiskAgentConfig`:
- `model: str = "gpt-5.1"`
- `batch_size: int = 5` — markets per parallel LLM call
- `max_concurrent_batches: int = 10` — semaphore limit
- `per_batch_timeout: float = 45.0` — timeout per batch LLM call
- `reconciliation_timeout: float = 30.0` — timeout for reconciliation call
- `total_timeout: float = 90.0` — hard ceiling for entire pipeline
- `max_retries: int = 2`
- `retry_delay: float = 1.0`

### 3. `risk_management_agent/prompts.py` — Prompt Templates

**Two prompts:**

**`BATCH_ANALYSIS_PROMPT`** — Sent to each batch of ~5 markets:
- Receives full research context (summary, key findings, sentiment, main event)
- Receives its batch of markets with current prices
- Rules for BUY (underpriced), SELL (overpriced), HOLD (fair/uncertain)
- Confidence calibration criteria
- Requires rationale referencing specific key findings
- Emphasizes mispricing identification, not outcome prediction
- Favors HOLD when evidence is unclear
- JSON-only output

**`RECONCILIATION_PROMPT`** — Reviews all signals from all batches:
- Receives the main event + all batch signals concatenated
- Checks for logical inconsistencies (e.g., cumulative date markets should be monotonic)
- Can adjust signals and confidence, must explain any changes
- Produces the final signal list + overall_analysis summary
- JSON-only output

**Helper functions:** `build_key_findings_block()`, `build_markets_block()`, `format_batch_prompt()`, `format_reconciliation_prompt()`

### 4. `risk_management_agent/analyzer.py` — Batch Analysis

- `analyze_batch()` — single async OpenAI call for one batch of markets (no web_search tool)
- Returns parsed JSON with signals for those markets
- Markdown fence stripping for JSON parsing
- `analyze_batch_with_retry()` — retry wrapper
- `build_fallback_batch()` — returns HOLD signals with low confidence if batch fails

### 5. `risk_management_agent/reconciler.py` — Cross-Batch Consistency

- `reconcile_signals()` — takes all batch results, calls LLM to check consistency
- Can adjust signals that are logically inconsistent across batches
- Produces final ordered signal list + overall_analysis
- `reconcile_with_retry()` — retry wrapper
- Fallback: if reconciliation fails, return original batch signals as-is with a concatenated analysis

### 6. `risk_management_agent/agent.py` — Orchestrator

`RiskManagementAgent` class:
- Constructor takes config + optional API key, creates `AsyncOpenAI` client
- `async run(input) -> RiskAnalysisOutput` with hard timeout wrapper
- Pipeline:
  1. Split `input.markets` into batches of `config.batch_size`
  2. Fire all batches concurrently via `asyncio.gather` (with semaphore)
  3. Collect results, handle per-batch failures with fallback
  4. Pass all signals to reconciler for consistency check
  5. Assemble final `RiskAnalysisOutput`
- Safe enum parsing with conservative defaults (unknown → HOLD / LOW)

### 7. `risk_management_agent/__init__.py` — Exports

Exports: `RiskManagementAgent`, `RiskAnalysisInput`, `RiskAnalysisOutput`, `RiskAgentConfig`, `DEFAULT_RISK_CONFIG`

### 8. `run_risk.py` — CLI Runner

Same pattern as `run.py`: argparse with `--input`, `--stdin`, `--model`, `--timeout`, `--output`. Built-in sample input with ~10 markets (Iran strike scenario with date-based markets at varying prices).

---

## File to Modify

### 9. `api.py` — Add `/risk` Endpoint

- Add import for `risk_management_agent`
- New `POST /risk` endpoint matching the existing `/research` pattern (body + model/timeout query params)
- Returns `RiskAnalysisOutput`

---

## Pipeline Flow

```
Input (20 markets)
    │
    ├─ Batch 1 (markets 1-5)  ──→ LLM call ──→ 5 signals
    ├─ Batch 2 (markets 6-10) ──→ LLM call ──→ 5 signals     (all parallel)
    ├─ Batch 3 (markets 11-15)──→ LLM call ──→ 5 signals
    └─ Batch 4 (markets 16-20)──→ LLM call ──→ 5 signals
                                       │
                                       ▼
                              Reconciliation LLM call
                              (check consistency across batches)
                                       │
                                       ▼
                              RiskAnalysisOutput (20 signals)
```

**Estimated timing** for 20 markets:
- Batch analysis: ~15-25s (all 4 run in parallel)
- Reconciliation: ~10-15s
- Total: ~25-40s (vs ~60-90s for a single call with all 20)

---

## Verification

1. **CLI test**: `cd agents && python run_risk.py` (uses built-in sample)
2. **API test**: Start server (`uvicorn api:app --port 8000`), POST to `/risk` with test JSON
3. **Check signals**: Verify signals are logical given research sentiment
4. **Check consistency**: Verify reconciler catches inconsistencies (e.g., cumulative date markets)
5. **Check fallback**: Break LLM call to verify graceful degradation (all HOLD)
6. **Check parallelism**: Observe timing — 20 markets should complete in ~30s, not ~120s
7. **Health check**: Verify `/health` still works after api.py changes
