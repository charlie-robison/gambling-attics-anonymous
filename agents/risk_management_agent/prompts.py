"""LLM prompt templates for the risk management agent.

Two prompts:
1. BATCH_ANALYSIS_PROMPT  – sent to each batch of ~5 markets in parallel.
2. RECONCILIATION_PROMPT  – reviews all predictions for cross-batch consistency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas import Market

# ---------------------------------------------------------------------------
# Batch analysis prompt
# ---------------------------------------------------------------------------

BATCH_ANALYSIS_PROMPT = """\
You are an expert prediction market analyst. Your job is to analyze research \
findings and predict whether each market's event will happen by its specified \
date.

=== MAIN EVENT ===
{main_event_title}
{main_event_description}

=== RESEARCH SUMMARY ===
{research_summary}

=== KEY FINDINGS ===
{key_findings_block}

=== OVERALL RESEARCH SENTIMENT ===
{sentiment}

=== MARKETS TO ANALYZE (this batch) ===
{markets_block}

---

For each market, predict YES or NO:
- **YES** = the event WILL happen on or before this market's date
- **NO**  = the event will NOT happen by this market's date

Return ONLY valid JSON (no markdown fences, no commentary) matching this schema:

{{
  "signals": [
    {{
      "market_id": "<id>",
      "market_title": "<title>",
      "prediction": "<yes|no>",
      "confidence": "<high|medium|low>",
      "rationale": "<2-4 sentence explanation>"
    }}
  ]
}}

PREDICTION RULES:

1. **YES** – research evidence indicates the event is likely to occur by \
   this date. There are concrete catalysts, timelines, or indicators \
   pointing to action within this window.

2. **NO** – research evidence indicates the event is unlikely to occur by \
   this date. There is insufficient evidence of imminent action, active \
   de-escalation, or the time window is too narrow for the expected \
   development timeline.

CONFIDENCE LEVELS:
- HIGH:   multiple strong findings converge, clear directional evidence
- MEDIUM: moderate evidence, some contradictions, reasonable uncertainty
- LOW:    weak or mixed evidence, high uncertainty, limited data

REQUIREMENTS:
- Every rationale MUST reference specific key findings that support the prediction.
- Consider time horizons carefully: a NO for "today" does not contradict a \
  YES for "within 30 days" — the same event can be unlikely near-term but \
  likely over a longer window.
- Ground every prediction in the research, not speculation.
- If the current market price is provided, note whether your prediction \
  agrees or disagrees with the market's implied probability.
"""


# ---------------------------------------------------------------------------
# Reconciliation prompt
# ---------------------------------------------------------------------------

RECONCILIATION_PROMPT = """\
You are a senior analyst reviewing predictions produced by junior analysts. \
Your task is to check for LOGICAL CONSISTENCY across all predictions for \
markets under one event, and produce a final consolidated output.

=== MAIN EVENT ===
{main_event_title}
{main_event_description}

=== RESEARCH SENTIMENT ===
{sentiment}

=== ALL PREDICTIONS FROM ANALYSTS ===
{all_signals_block}

---

Review the predictions above for consistency. Common issues to check:

1. **Cumulative / date-based markets**: If "by Feb 22" is YES, then \
   "by Feb 23" MUST also be YES (if it happens by the 22nd, it has \
   also happened by the 23rd). Similarly if "by Feb 25" is NO, then \
   "by Feb 24" should also be NO.

2. **Transition point**: There should be a logical transition from NO to \
   YES as the time window expands. Identify where the evidence tips the \
   balance.

3. **Confidence calibration**: Confidence should generally be highest for \
   the clearest cases (very near-term NO, or very long-term YES) and \
   lower near the transition point.

4. **Rationale alignment**: Ensure rationales don't contradict each other \
   across markets.

You may adjust predictions, confidence levels, or rationale where needed. \
If you change a prediction, explain why in the rationale.

Return ONLY valid JSON (no markdown fences, no commentary):

{{
  "signals": [
    {{
      "market_id": "<id>",
      "market_title": "<title>",
      "prediction": "<yes|no>",
      "confidence": "<high|medium|low>",
      "rationale": "<2-4 sentence explanation>"
    }}
  ],
  "overall_analysis": "<2-4 paragraph summary of analysis across all markets>"
}}

Include ALL markets in the output, even those you did not change.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def build_key_findings_block(key_findings: list[str]) -> str:
    """Format key findings as a numbered list."""
    return "\n".join(f"{i + 1}. {f}" for i, f in enumerate(key_findings))


def build_markets_block(markets: list[Market]) -> str:
    """Format a list of markets for the prompt."""
    parts: list[str] = []
    for m in markets:
        lines = [
            f"Market ID: {m.id}",
            f"Question: {m.title}",
        ]
        if m.current_price is not None:
            pct = m.current_price * 100
            lines.append(
                f"Current Price: {m.current_price:.3f} "
                f"(implied probability: {pct:.1f}%)"
            )
        else:
            lines.append("Current Price: Not available")
        if m.description:
            lines.append(f"Description: {m.description}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def build_signals_block(all_signals: list[dict]) -> str:
    """Format collected predictions from all batches for the reconciliation prompt."""
    parts: list[str] = []
    for s in all_signals:
        price_info = ""
        if s.get("current_price") is not None:
            price_info = f" | Price: {s['current_price']:.3f}"
        prediction = s.get("prediction", "?").upper()
        parts.append(
            f"Market: {s['market_title']} (ID: {s['market_id']}){price_info}\n"
            f"  Prediction: {prediction} | "
            f"Confidence: {s['confidence'].upper()}\n"
            f"  Rationale: {s['rationale']}"
        )
    return "\n\n".join(parts)


def format_batch_prompt(
    main_event_title: str,
    main_event_description: str | None,
    research_summary: str,
    key_findings: list[str],
    sentiment: str,
    markets: list[Market],
) -> str:
    """Build the complete batch analysis prompt."""
    return BATCH_ANALYSIS_PROMPT.format(
        main_event_title=main_event_title,
        main_event_description=main_event_description or "No additional description.",
        research_summary=research_summary,
        key_findings_block=build_key_findings_block(key_findings),
        sentiment=sentiment.upper(),
        markets_block=build_markets_block(markets),
    )


def format_reconciliation_prompt(
    main_event_title: str,
    main_event_description: str | None,
    sentiment: str,
    all_signals: list[dict],
) -> str:
    """Build the reconciliation prompt with all predictions."""
    return RECONCILIATION_PROMPT.format(
        main_event_title=main_event_title,
        main_event_description=main_event_description or "No additional description.",
        sentiment=sentiment.upper(),
        all_signals_block=build_signals_block(all_signals),
    )
