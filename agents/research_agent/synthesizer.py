"""Synthesis stage: combine raw research into structured analysis.

Uses GPT-5.1 **without** web search (pure reasoning) so it is faster and
avoids the known JSON-corruption bug with ``web_search_preview`` +
structured outputs.
"""

from __future__ import annotations

import asyncio
import json

from openai import AsyncOpenAI

from .config import AgentConfig, DEFAULT_CONFIG
from .prompts import SYNTHESIS_NO_MAIN_EVENT_PROMPT, SYNTHESIS_PROMPT
from .researcher import RawResearchResult
from .schemas import MainEvent, SubEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_sub_events_block(
    sub_events: list[SubEvent],
    sub_event_results: list[RawResearchResult],
) -> str:
    """Build the text block describing all sub-event research for the prompt."""

    result_map = {r.event_id: r for r in sub_event_results}
    blocks: list[str] = []

    for se in sub_events:
        result = result_map.get(se.id)
        block = f"\n--- SUB-EVENT: {se.title} ---\nID: {se.id}\n"

        if result and result.error is None:
            block += f"Research Findings:\n{result.research_text}\n"
        elif result and result.error:
            block += f"Research Error: {result.error}\n"
        else:
            block += "No research available.\n"

        blocks.append(block)

    return "\n".join(blocks)


# ---------------------------------------------------------------------------
# Main synthesis function
# ---------------------------------------------------------------------------


async def synthesize(
    client: AsyncOpenAI,
    main_event: MainEvent | None,
    sub_events: list[SubEvent],
    main_event_result: RawResearchResult | None,
    sub_event_results: list[RawResearchResult],
    config: AgentConfig = DEFAULT_CONFIG,
) -> dict:
    """Synthesise all research into a structured analysis dict.

    Returns a ``dict`` that the orchestrator maps onto the output Pydantic
    models.  Falls back to a minimal structure if the LLM call fails.
    """

    sub_events_block = _build_sub_events_block(sub_events, sub_event_results)

    if main_event is not None:
        # Build main-event research block
        if main_event_result and main_event_result.error is None:
            main_research_block = main_event_result.research_text
        elif main_event_result and main_event_result.error:
            main_research_block = f"Research Error: {main_event_result.error}"
        else:
            main_research_block = "No main event research available."

        prompt = SYNTHESIS_PROMPT.format(
            main_event_title=main_event.title,
            main_event_description=main_event.description or "",
            main_event_research_block=main_research_block,
            sub_events_research_block=sub_events_block,
        )
    else:
        prompt = SYNTHESIS_NO_MAIN_EVENT_PROMPT.format(
            sub_events_research_block=sub_events_block,
        )

    try:
        response = await asyncio.wait_for(
            client.responses.create(
                model=config.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are a JSON-only response bot. "
                            "Return ONLY valid JSON, no markdown fences, "
                            "no explanation outside the JSON object."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            ),
            timeout=config.synthesis_timeout,
        )

        raw_text = response.output_text.strip()

        # Strip markdown fences if the model adds them anyway
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3].strip()

        return json.loads(raw_text)

    except (asyncio.TimeoutError, json.JSONDecodeError, Exception) as exc:
        return _build_fallback(
            main_event,
            sub_events,
            main_event_result,
            sub_event_results,
            str(exc),
        )


# ---------------------------------------------------------------------------
# Fallback if synthesis LLM call fails
# ---------------------------------------------------------------------------


def _build_fallback(
    main_event: MainEvent | None,
    sub_events: list[SubEvent],
    main_event_result: RawResearchResult | None,
    sub_event_results: list[RawResearchResult],
    error_msg: str,
) -> dict:
    """Return a minimal valid synthesis dict from raw research text."""

    result_map = {r.event_id: r for r in sub_event_results}

    sub_analyses = []
    for se in sub_events:
        r = result_map.get(se.id)
        sub_analyses.append(
            {
                "sub_event_id": se.id,
                "sub_event_title": se.title,
                "summary": (
                    r.research_text[:3000]
                    if r and not r.error
                    else f"Research unavailable: {r.error if r else 'unknown'}"
                ),
                "key_findings": ["See raw research text above"],
                "sentiment": "neutral",
                "sentiment_rationale": "Automated fallback – synthesis LLM call failed",
            }
        )

    result: dict = {
        "sub_event_analyses": sub_analyses,
        "synthesis": (
            f"Synthesis failed ({error_msg}). "
            "Raw research is included per sub-event above."
        ),
    }

    if main_event and main_event_result:
        result["main_event_research"] = {
            "summary": (
                main_event_result.research_text[:3000]
                if not main_event_result.error
                else f"Research unavailable: {main_event_result.error}"
            ),
            "key_findings": ["See raw research text"],
            "sentiment": "neutral",
            "sentiment_rationale": "Automated fallback",
        }
        result["relationships"] = []

    return result
