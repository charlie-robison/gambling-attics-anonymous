# Research Agent API - Integration Guide

This doc tells you everything you need to call the research agent from the MCP server.

## Quick Start

```bash
cd agents
pip3 install -r requirements.txt
python3 -m uvicorn api:app --host 0.0.0.0 --port 8000
```

Server runs at `http://localhost:8000`. Auto-generated docs at `http://localhost:8000/docs`.

---

## Endpoints

### `GET /health`

Health check. Returns `{"status": "ok"}` if the server is running.

### `POST /research`

Run the full research pipeline. Takes ~1-2 minutes depending on number of sub-events.

**Optional query params:**
| Param | Default | Description |
|-------|---------|-------------|
| `model` | `gpt-5.1` | OpenAI model to use |
| `timeout` | `180` | Total pipeline timeout in seconds |

---

## Request Body

```json
{
  "main_event": {
    "title": "string (required)",
    "description": "string (optional)"
  },
  "sub_events": [
    {
      "title": "string (required)",
      "description": "string (optional)"
    }
  ]
}
```

### Field Details

| Field | Required | Description |
|-------|----------|-------------|
| `main_event` | No | The parent event that groups sub-events. Omit if sub-events are independent. |
| `main_event.title` | Yes (if main_event provided) | Event name, e.g. "US strikes Iran by...?" |
| `main_event.description` | No | Longer description / resolution criteria |
| `sub_events` | Yes | Array of 1+ market questions to research |
| `sub_events[].title` | Yes | The specific question, e.g. "Khamenei out as Supreme Leader?" |
| `sub_events[].description` | No | Resolution criteria, context, etc. |

> **Note:** `sub_events[].id` is auto-generated from the title. You don't need to provide it.

---

## Response Body

```json
{
  "main_event_research": {
    "event_title": "US strikes Iran by...?",
    "summary": "2-4 paragraph research summary...",
    "key_findings": [
      "Finding 1",
      "Finding 2"
    ],
    "news_links": [
      {
        "title": "Article title",
        "url": "https://...",
        "snippet": "Brief excerpt (optional)",
        "published_date": "2026-02-20 (optional)",
        "source_name": "Reuters (optional)"
      }
    ],
    "sentiment": "bearish",
    "sentiment_rationale": "Explanation of why this sentiment was assigned"
  },
  "sub_event_research": [
    {
      "sub_event_id": "khamenei-out-as-supreme-leader-of-iran-in-2026",
      "sub_event_title": "Khamenei out as Supreme Leader of Iran in 2026?",
      "summary": "2-4 paragraph research summary...",
      "key_findings": ["Finding 1", "Finding 2"],
      "news_links": [{"title": "...", "url": "...", "snippet": "...", "published_date": "...", "source_name": "..."}],
      "sentiment": "very_bearish",
      "sentiment_rationale": "Explanation..."
    }
  ],
  "relationships": [
    {
      "sub_event_id": "khamenei-out-as-supreme-leader-of-iran-in-2026",
      "sub_event_title": "Khamenei out as Supreme Leader of Iran in 2026?",
      "relationship_summary": "How this sub-event connects to the main event",
      "influencing_news": "What news around this sub-event could influence the main event"
    }
  ],
  "synthesis": "3-5 paragraph overall narrative tying everything together...",
  "research_timestamp": "2026-02-21T15:30:00+00:00",
  "disclaimer": "This research is for informational purposes only..."
}
```

### Response Field Details

| Field | Type | Present When |
|-------|------|-------------|
| `main_event_research` | object or null | Only when `main_event` was provided in request |
| `sub_event_research` | array | Always (one entry per sub-event) |
| `relationships` | array or null | Only when `main_event` was provided |
| `synthesis` | string | Always |
| `research_timestamp` | string (ISO 8601) | Always |
| `disclaimer` | string | Always |

### Sentiment Values

One of: `very_bearish`, `bearish`, `neutral`, `bullish`, `very_bullish`

---

## Example: curl

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{
    "main_event": {
      "title": "US strikes Iran by...?",
      "description": "Will the US initiate a strike on Iranian soil?"
    },
    "sub_events": [
      {
        "title": "Khamenei out as Supreme Leader of Iran in 2026?",
        "description": "Will Khamenei be removed from power by Dec 31, 2026?"
      },
      {
        "title": "Khamenei out as Supreme Leader of Iran by June 30?",
        "description": "Will Khamenei be removed from power by June 30, 2026?"
      }
    ]
  }'
```

With custom model/timeout:
```bash
curl -X POST "http://localhost:8000/research?model=gpt-5.1&timeout=300" \
  -H "Content-Type: application/json" \
  -d @test_input.json
```

---

## Example: TypeScript (fetch)

```typescript
interface ResearchRequest {
  main_event?: {
    title: string;
    description?: string;
  };
  sub_events: Array<{
    title: string;
    description?: string;
  }>;
}

async function runResearch(input: ResearchRequest) {
  const response = await fetch("http://localhost:8000/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    throw new Error(`Research API error: ${response.status}`);
  }

  return await response.json();
}

// Usage
const result = await runResearch({
  main_event: {
    title: "US strikes Iran by...?",
    description: "Will the US initiate a strike on Iranian soil?",
  },
  sub_events: [
    {
      title: "Khamenei out as Supreme Leader of Iran in 2026?",
      description: "Will Khamenei be removed from power by Dec 31, 2026?",
    },
  ],
});

console.log(result.synthesis);
console.log(result.sub_event_research[0].sentiment);
```

---

## Error Handling

The agent **never crashes** - it always returns valid JSON:

| Scenario | What Happens |
|----------|-------------|
| Single research call fails | That sub-event gets minimal data, others unaffected |
| Synthesis LLM call fails | Fallback builds output from raw research text |
| Total timeout (default 180s) | Returns partial results with timeout message in `synthesis` |
| Invalid input JSON | HTTP 422 with Pydantic validation errors |

---

## Environment

The server needs `OPENAI_API_KEY` set. It reads from `agents/.env` automatically:

```
OPENAI_API_KEY=sk-proj-...
```
