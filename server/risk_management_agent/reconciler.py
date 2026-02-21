"""Cross-batch signal reconciliation.

After parallel batch analysis, this module reviews all signals together
for logical consistency (e.g. cumulative date-based markets should have
monotonically non-decreasing signals).
"""

from __future__ import annotations

import asyncio
import json
import re
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


def _extract_chat_text(response: object) -> str:
    """Extract plain text from Chat Completions responses."""
    choices = getattr(response, "choices", None)
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    chunks.append(str(text))
            else:
                text = getattr(item, "text", None)
                if text:
                    chunks.append(str(text))
        return "\n".join(chunks)
    return str(content)


def _strip_markdown_fences(raw_text: str) -> str:
    """Strip markdown code fences if the model wraps JSON in them."""
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3].strip()
    return raw_text


def _parse_json_from_text(raw_text: str) -> dict:
    """Parse JSON from model output, tolerating wrapper text."""
    stripped = _strip_markdown_fences(raw_text).strip()
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if not match:
        raise json.JSONDecodeError("No JSON object found", stripped, 0)
    parsed = json.loads(match.group(0))
    return parsed if isinstance(parsed, dict) else {}


async def _run_reconciliation_completion(
    client: AsyncOpenAI,
    prompt: str,
    config: RiskAgentConfig,
) -> str:
    """Run reconciliation via Responses API when available, else Chat Completions."""
    system_msg = (
        "You are a JSON-only response bot for risk "
        "reconciliation. Return ONLY valid JSON, no "
        "markdown fences, no explanation outside the "
        "JSON object."
    )

    if hasattr(client, "responses"):
        response = await client.responses.create(
            model=config.model,
            input=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
        )
        return response.output_text.strip()

    try:
        response = await client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
    except Exception:
        response = await client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
        )
    return _extract_chat_text(response).strip()


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
        raw_text = await asyncio.wait_for(
            _run_reconciliation_completion(client, prompt, config),
            timeout=config.reconciliation_timeout,
        )
        parsed = _parse_json_from_text(raw_text)

        raw_signals = parsed.get("signals", [])
        signals = (
            [dict(sig) for sig in raw_signals if isinstance(sig, dict)]
            if isinstance(raw_signals, list)
            else []
        )
        overall_analysis = parsed.get("overall_analysis", "")
        if not isinstance(overall_analysis, str):
            overall_analysis = str(overall_analysis)

        return ReconciliationResult(
            signals=signals,
            overall_analysis=overall_analysis,
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
