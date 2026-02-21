"""Preprocessor: extract and distil research agent output into risk agent input.

Pure Python — no LLM calls.  Takes the raw ``RiskManagementInput`` (full
research JSON + main event + markets) and produces a compact
``RiskAnalysisInput`` that the LLM prompts can work with efficiently.

Extraction rules
----------------
1. **research_summary** — the synthesis field from the research output.
   This is the best single-field summary because it already merges
   main-event research, sub-event research, and cross-event relationships
   into one coherent narrative.

2. **key_findings** — collected from:
   a. main_event_research.key_findings  (if present)
   b. each sub_event_research[].key_findings
   De-duplicated by exact string match, capped at 20 findings.

3. **sentiment** — taken from main_event_research.sentiment if present,
   otherwise derived by averaging sub-event sentiments.

4. **main_event** and **markets** — passed through as-is from the MCP
   payload (no transformation needed).
"""

from __future__ import annotations

from .schemas import (
    MainEventInfo,
    Market,
    RiskAnalysisInput,
    RiskManagementInput,
    SentimentRating,
)

# Maximum key findings to forward to the LLM
_MAX_KEY_FINDINGS = 20

# Ordered for numeric averaging
_SENTIMENT_ORDER: list[str] = [
    "very_bearish",
    "bearish",
    "neutral",
    "bullish",
    "very_bullish",
]


def preprocess(raw: RiskManagementInput) -> RiskAnalysisInput:
    """Transform raw MCP payload into the compact LLM-ready input.

    This is the single entry-point the agent calls.
    """
    research = raw.research_output

    research_summary = _extract_summary(research)
    key_findings = _extract_key_findings(research)
    sentiment = _extract_sentiment(research)

    return RiskAnalysisInput(
        research_summary=research_summary,
        key_findings=key_findings,
        sentiment=sentiment,
        main_event=raw.main_event,
        markets=raw.markets,
    )


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def _extract_summary(research: dict) -> str:
    """Pull the best available summary from the research output.

    Priority:
    1. synthesis  (cross-event narrative — best single source)
    2. main_event_research.summary  (fallback if synthesis missing)
    3. Concatenated sub-event summaries  (last resort)
    """
    # 1. Synthesis
    synthesis = research.get("synthesis")
    if synthesis and isinstance(synthesis, str) and synthesis.strip():
        return synthesis.strip()

    # 2. Main event summary
    main = research.get("main_event_research")
    if main and isinstance(main, dict):
        summary = main.get("summary")
        if summary and isinstance(summary, str) and summary.strip():
            return summary.strip()

    # 3. Concatenated sub-event summaries
    parts: list[str] = []
    for sub in research.get("sub_event_research", []):
        if isinstance(sub, dict):
            s = sub.get("summary", "")
            if s:
                title = sub.get("sub_event_title", "")
                parts.append(f"[{title}] {s}" if title else s)
    if parts:
        return "\n\n".join(parts)

    return "No research summary available."


def _extract_key_findings(research: dict) -> list[str]:
    """Collect key findings from main event + all sub-events.

    De-duplicates by exact string match and caps at _MAX_KEY_FINDINGS.
    Main event findings come first (they're most relevant to the
    overarching event the user is trading on).
    """
    findings: list[str] = []
    seen: set[str] = set()

    def _add(items: list) -> None:
        for item in items:
            if isinstance(item, str) and item.strip() and item not in seen:
                seen.add(item)
                findings.append(item)

    # Main event findings first
    main = research.get("main_event_research")
    if main and isinstance(main, dict):
        _add(main.get("key_findings", []))

    # Sub-event findings
    for sub in research.get("sub_event_research", []):
        if isinstance(sub, dict):
            _add(sub.get("key_findings", []))

    # Cap
    findings = findings[:_MAX_KEY_FINDINGS]

    # Safety: at least one finding required by the schema
    if not findings:
        findings = ["No key findings available from research."]

    return findings


def _extract_sentiment(research: dict) -> SentimentRating:
    """Determine the overall sentiment.

    Priority:
    1. main_event_research.sentiment  (directly relevant)
    2. Average of sub-event sentiments  (fallback)
    3. neutral  (safe default)
    """
    # 1. Main event sentiment
    main = research.get("main_event_research")
    if main and isinstance(main, dict):
        raw_sentiment = main.get("sentiment")
        parsed = _parse_sentiment(raw_sentiment)
        if parsed is not None:
            return parsed

    # 2. Average sub-event sentiments
    sub_sentiments: list[int] = []
    for sub in research.get("sub_event_research", []):
        if isinstance(sub, dict):
            parsed = _parse_sentiment(sub.get("sentiment"))
            if parsed is not None:
                sub_sentiments.append(_SENTIMENT_ORDER.index(parsed.value))

    if sub_sentiments:
        avg_idx = round(sum(sub_sentiments) / len(sub_sentiments))
        avg_idx = max(0, min(avg_idx, len(_SENTIMENT_ORDER) - 1))
        return SentimentRating(_SENTIMENT_ORDER[avg_idx])

    # 3. Default
    return SentimentRating.NEUTRAL


def _parse_sentiment(value: object) -> SentimentRating | None:
    """Safely parse a sentiment value from the research JSON."""
    if not isinstance(value, str):
        return None
    try:
        return SentimentRating(value.lower().strip())
    except ValueError:
        return None
