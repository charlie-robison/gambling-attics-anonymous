"""Cross-batch signal reconciliation.

After parallel batch analysis, this module reviews all signals together
for logical consistency (e.g. cumulative date-based markets should have
monotonically non-decreasing signals).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Callable, Coroutine

from openai import AsyncOpenAI

from .config import DEFAULT_RISK_CONFIG, RiskAgentConfig
from .prompts import format_reconciliation_prompt


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class ReconciliationResult:
    """Output from the reconciliation LLM call."""

    signals: list[dict] = field(default_factory=list)
    overall_analysis: str = ""
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and len(self.signals) > 0


# ---------------------------------------------------------------------------
# Core reconciliation
# ---------------------------------------------------------------------------


async def reconcile_signals(
    client: AsyncOpenAI,
    main_event_title: str,
    main_event_description: str | None,
    sentiment: str,
    all_signals: list[dict],
    config: RiskAgentConfig = DEFAULT_RISK_CONFIG,
) -> ReconciliationResult:
    """Review all batch signals for cross-batch consistency.

    Returns a ReconciliationResult with the final (possibly adjusted)
    signal list and an overall analysis summary.
    """

    prompt = format_reconciliation_prompt(
        main_event_title=main_event_title,
        main_event_description=main_event_description,
        sentiment=sentiment,
        all_signals=all_signals,
    )

    try:
        response = await asyncio.wait_for(
            client.responses.create(
                model=config.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are a JSON-only response bot for risk "
                            "reconciliation. Return ONLY valid JSON, no "
                            "markdown fences, no explanation outside the "
                            "JSON object."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            ),
            timeout=config.reconciliation_timeout,
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

        return ReconciliationResult(
            signals=parsed.get("signals", []),
            overall_analysis=parsed.get("overall_analysis", ""),
        )

    except asyncio.TimeoutError:
        return ReconciliationResult(
            error=(
                f"Reconciliation timed out after "
                f"{config.reconciliation_timeout}s"
            ),
        )
    except json.JSONDecodeError as exc:
        return ReconciliationResult(
            error=f"Reconciliation JSON parse error: {exc}",
        )
    except Exception as exc:
        return ReconciliationResult(
            error=f"Reconciliation failed: {exc}",
        )


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------


async def reconcile_with_retry(
    coro_factory: Callable[[], Coroutine[None, None, ReconciliationResult]],
    config: RiskAgentConfig = DEFAULT_RISK_CONFIG,
) -> ReconciliationResult:
    """Retry reconciliation up to ``config.max_retries`` times on failure."""

    last_result: ReconciliationResult | None = None
    for attempt in range(1 + config.max_retries):
        result = await coro_factory()
        if result.success:
            return result
        last_result = result
        if attempt < config.max_retries:
            await asyncio.sleep(config.retry_delay)
    return last_result  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Fallback: skip reconciliation, pass through batch signals as-is
# ---------------------------------------------------------------------------


def build_fallback_reconciliation(
    all_signals: list[dict],
    sentiment: str,
    error_msg: str,
) -> ReconciliationResult:
    """Return batch signals unmodified when reconciliation fails."""

    return ReconciliationResult(
        signals=all_signals,
        overall_analysis=(
            f"Cross-batch reconciliation was unavailable ({error_msg}). "
            f"Signals below are from independent batch analysis and have "
            f"not been checked for cross-market consistency. "
            f"Research sentiment is {sentiment}. "
            f"Manual review is recommended before acting on these signals."
        ),
    )
