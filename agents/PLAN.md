# Polymarket Research Agent - Implementation Plan

## Context

We're at the Manufact MCP Apps Hackathon building a Polymarket MCP that connects prediction market data to ChatGPT. The MCP server (TypeScript) handles Polymarket API calls and UI. **Our task**: build the **research agent** - a standalone Python module in `agents/` that takes event JSON from the MCP, performs parallel web research using GPT-5.1, and returns structured analysis JSON back.

The Manufact agent SDK is **not needed** - we're building a plain Python async module with the OpenAI SDK directly, which gives us full control and no framework limitations.

## Architecture Overview

```
MCP Server (TypeScript) ──JSON──> Research Agent (Python) ──JSON──> MCP Server
                                       │
                                  3-Stage Pipeline:
                                  1. Parallel web research (async)
                                  2. LLM synthesis (reasoning only)
                                  3. Output assembly (pure Python)
```

**Speed strategy**: All research calls run simultaneously via `asyncio.gather()`. Uses OpenAI's **agentic search** mode (model actively manages multiple searches, analyzes results, decides if more searching needed). Each call produces ~1-2 pages of research in ~30-90s. All calls run in parallel, so total Stage 1 time = slowest single call, not sum of all calls. Stage 2 synthesis adds ~15-30s. **Total: ~1-2 minutes** for any number of sub-events.

*Why not deep research mode?* Deep research (the ChatGPT feature) takes 3-10 min per query and isn't available via the standard Responses API. Agentic search with `search_context_size: "high"` is the deepest mode available through the API and produces thorough, multi-source research.

## File Structure

All code goes in the existing `agents/` directory:

```
agents/
├── research_agent/
│   ├── __init__.py          # Package exports
│   ├── agent.py             # Main orchestrator - ResearchAgent class
│   ├── researcher.py        # Individual event research (GPT-5.1 + web_search_preview)
│   ├── synthesizer.py       # Cross-event synthesis (GPT-5.1, no web search)
│   ├── schemas.py           # Pydantic input/output schemas
│   ├── prompts.py           # All LLM prompt templates
│   └── config.py            # Configuration (model, timeouts, concurrency)
├── requirements.txt         # openai, pydantic, python-dotenv
└── run.py                   # CLI entry point for testing
```

## Implementation Steps

### Step 1: Create `schemas.py` - Input/Output Data Models

**Input schemas (kept simple - just what the research agent needs):**
- `ResearchInput` - top level with optional `main_event: MainEvent` and required `sub_events: list[SubEvent]`
- `MainEvent` - fields: `title`, `description` (optional)
- `SubEvent` - fields: `id`, `title`, `description` (optional)

That's it for inputs. The research agent only needs to know *what* to research (title + description). All market data (prices, volume, liquidity, outcomes) is irrelevant to the research task - that's handled by other parts of the MCP.

**Output schemas:**
- `ResearchOutput` - top level with `main_event_research`, `sub_event_research`, `relationships`, `synthesis`, `research_timestamp`, `disclaimer`
- `MainEventResearch` - `event_title`, `summary` (1-2 pages), `key_findings`, `news_links`, `sentiment`, `sentiment_rationale`
- `SubEventResearch` - `sub_event_id`, `sub_event_title`, `summary` (1-2 pages), `key_findings`, `news_links`, `sentiment`, `sentiment_rationale`
- `SubEventRelationship` - `sub_event_id`, `sub_event_title`, `relationship_summary`, `influencing_news` (what news/developments around this sub-event could influence the main event and how)
- `NewsLink` - `title`, `url`, `snippet`, `published_date`, `source_name`
- `SentimentRating` - enum: `very_bearish`, `bearish`, `neutral`, `bullish`, `very_bullish`

### Step 2: Create `config.py` - Agent Configuration

Frozen dataclass with:
- `model`: `"gpt-5.1"`
- `search_context_size`: `"high"` (maximizes depth of agentic search)
- `per_research_timeout`: 90s per individual research call (agentic search can take 30-90s for thorough results)
- `synthesis_timeout`: 60s for synthesis call (needs time to process multiple pages of research)
- `total_timeout`: 180s hard ceiling (3 min max for entire pipeline)
- `max_concurrent_research`: 10 (semaphore limit)
- `max_retries`: 2 with 1s delay

### Step 3: Create `prompts.py` - Prompt Templates

Four prompt templates:
1. **`MAIN_EVENT_RESEARCH_PROMPT`** - instructs GPT to do thorough research on a main event: latest news, expert opinions, upcoming catalysts, background context. Should produce 1-2 pages of research with inline source citations.
2. **`SUB_EVENT_RESEARCH_PROMPT`** - instructs GPT to research a specific sub-event/market question: direct evidence, recent developments, quantitative data, expert forecasts. Should produce 1-2 pages.
3. **`SYNTHESIS_PROMPT`** - takes all raw research, produces structured JSON with analysis, sentiment, and relationship analysis including what news around each sub-event would influence the main event (when main event exists)
4. **`SYNTHESIS_NO_MAIN_EVENT_PROMPT`** - variant for when there's no main event, just independent sub-events

### Step 4: Create `researcher.py` - Parallel Web Research

Key components:
- `RawResearchResult` dataclass - holds raw text (~1-2 pages), extracted news links, error state
- `research_main_event()` - async function using `client.responses.create()` with `web_search_preview` tool
- `research_sub_event()` - same pattern for sub-events
- `_extract_news_links_from_response()` - parses `response.output` items to extract `url_citation` annotations as `NewsLink` objects
- `research_with_retry()` - retry wrapper taking a coroutine factory

**Important**: Uses `responses.create()` NOT `responses.parse()` for web search calls (known JSON corruption bug with `web_search_preview` + structured outputs).

### Step 5: Create `synthesizer.py` - Research Synthesis

- `synthesize()` - takes all raw results, builds prompt with concatenated research text, calls GPT-5.1 **without** web search (pure reasoning, faster)
- Returns parsed JSON dict with analysis structure
- `_build_fallback_synthesis()` - if synthesis LLM call fails, returns minimal valid structure from raw research text
- Uses system message `"You are a JSON-only response bot"` to ensure clean JSON output

### Step 6: Create `agent.py` - Main Orchestrator

`ResearchAgent` class with:
- `__init__(config, api_key)` - creates `AsyncOpenAI` client
- `run(input_data) -> ResearchOutput` - public entry point with total timeout wrapper
- `_run_pipeline()` - executes 3 stages:
  - **Stage 1**: Creates async tasks for main event + all sub-events, runs via `asyncio.gather()` with semaphore. All run in parallel.
  - **Stage 2**: Passes all raw results to `synthesize()`
  - **Stage 3**: `_assemble_output()` merges news links from Stage 1 + analysis from Stage 2 into final `ResearchOutput`

### Step 7: Create `__init__.py`, `requirements.txt`, `run.py`

- `__init__.py` - exports `ResearchAgent`, `ResearchInput`, `ResearchOutput`
- `requirements.txt` - `openai>=1.60.0`, `pydantic>=2.0.0`, `python-dotenv>=1.0.0`
- `run.py` - CLI with `--input file.json`, `--stdin`, or built-in sample data. Outputs JSON to stdout.

## Error Handling Strategy

| Failure | Handling |
|---------|----------|
| Single research call timeout/error | Returns error `RawResearchResult`, other calls unaffected. Retried up to 2x. |
| Synthesis call fails | Fallback builds minimal output from raw research text |
| Total pipeline timeout (180s) | Returns minimal `ResearchOutput` with timestamp |
| Invalid input JSON | Pydantic `ValidationError` before pipeline starts |

The agent **never crashes** - always returns valid JSON.

## MCP Integration (for teammates)

The TypeScript MCP server can call the Python agent via subprocess:
```
echo '{"sub_events": [...]}' | python agents/run.py --stdin
```
Output is JSON on stdout, ready to parse and send to ChatGPT widget.

## Verification Plan

1. **Install deps**: `cd agents && pip install -r requirements.txt`
2. **Set API key**: `export OPENAI_API_KEY=sk-...`
3. **Run with sample data**: `python agents/run.py` (uses built-in sample)
4. **Run with custom input**: `python agents/run.py --input test_input.json`
5. **Run with pipe**: `echo '{"sub_events":[...]}' | python agents/run.py --stdin`
6. **Verify output**: Check JSON has `sub_event_research` array with substantial summaries, `synthesis` string, `news_links` with real URLs, valid `sentiment` values, `relationships` with `influencing_news`
7. **Verify speed**: Should complete in ~1-2 minutes for 2-5 sub-events
