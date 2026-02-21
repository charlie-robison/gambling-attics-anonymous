"""Batch market analysis using GPT-5.1 (no web search, pure reasoning).

Each batch receives the full research context and a subset of markets.
Multiple batches run concurrently for speed.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Callable, Coroutine

from openai import AsyncOpenAI

from .config import DEFAULT_RISK_CONFIG, RiskAgentConfig
from .prompts import format_batch_prompt
from .schemas import Market, RiskAnalysisInput


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class BatchResult:
    """Output from a single batch analysis LLM call."""

    batch_index: int
    signals: list[dict] = field(default_factory=list)
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and len(self.signals) > 0


# ---------------------------------------------------------------------------
# Core batch analysis
# ---------------------------------------------------------------------------


async def analyze_batch(
    client: AsyncOpenAI,
    input_data: RiskAnalysisInput,
    markets: list[Market],
    batch_index: int,
    config: RiskAgentConfig = DEFAULT_RISK_CONFIG,
) -> BatchResult:
    """Analyse a batch of markets and return trading signals.

    Uses the OpenAI Responses API *without* web search tools – pure
    reasoning over the pre-supplied research data.
    """

    prompt = format_batch_prompt(
        main_event_title=input_data.main_event.title,
        main_event_description=input_data.main_event.description,
        research_summary=input_data.research_summary,
        key_findings=input_data.key_findings,
        sentiment=input_data.sentiment.value,
        markets=markets,
    )

    try:
        response = await asyncio.wait_for(
            client.responses.create(
                model=config.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are a JSON-only response bot for trading "
                            "signal analysis. Return ONLY valid JSON, no "
                            "markdown fences, no explanation outside the "
                            "JSON object."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            ),
            timeout=config.per_batch_timeout,
        )

        raw_text = response.output_text.strip()

        # Strip markdown fences if the model adds them
        if raw_text.startswith("```"):
            raw_text = (
                raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text[3:]
            )
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3].strip()

        parsed = json.loads(raw_text)

        # Attach current_price from input for the reconciler
        price_map = {m.id: m.current_price for m in markets}
        for sig in parsed.get("signals", []):
            sig["current_price"] = price_map.get(sig.get("market_id"))

        return BatchResult(
            batch_index=batch_index,
            signals=parsed.get("signals", []),
        )

    except asyncio.TimeoutError:
        return BatchResult(
            batch_index=batch_index,
            error=f"Batch {batch_index} timed out after {config.per_batch_timeout}s",
        )
    except json.JSONDecodeError as exc:
        return BatchResult(
            batch_index=batch_index,
            error=f"Batch {batch_index} JSON parse error: {exc}",
        )
    except Exception as exc:
        return BatchResult(
            batch_index=batch_index,
            error=f"Batch {batch_index} failed: {exc}",
        )


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------


async def analyze_batch_with_retry(
    coro_factory: Callable[[], Coroutine[None, None, BatchResult]],
    config: RiskAgentConfig = DEFAULT_RISK_CONFIG,
) -> BatchResult:
    """Retry a batch analysis up to ``config.max_retries`` times on failure."""

    last_result: BatchResult | None = None
    for attempt in range(1 + config.max_retries):
        result = await coro_factory()
        if result.success:
            return result
        last_result = result
        if attempt < config.max_retries:
            await asyncio.sleep(config.retry_delay)
    return last_result  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Fallback for a failed batch
# ---------------------------------------------------------------------------


def build_fallback_batch(
    markets: list[Market],
    batch_index: int,
    error_msg: str,
) -> BatchResult:
    """Conservative fallback: NO with low confidence for every market."""

    signals = []
    for m in markets:
        signals.append(
            {
                "market_id": m.id,
                "market_title": m.title,
                "prediction": "no",
                "confidence": "low",
                "rationale": (
                    f"Analysis unavailable ({error_msg}). "
                    "Defaulting to NO until analysis can be completed."
                ),
                "current_price": m.current_price,
            }
        )
    return BatchResult(batch_index=batch_index, signals=signals)
