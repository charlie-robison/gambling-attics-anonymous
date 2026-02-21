"""Batch market analysis using GPT-5.1 (no web search, pure reasoning).

Each batch receives the full research context and a subset of markets.
Multiple batches run concurrently for speed.
"""

from __future__ import annotations

import asyncio
import json
import re
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


async def _run_batch_completion(
    client: AsyncOpenAI,
    prompt: str,
    config: RiskAgentConfig,
) -> str:
    """Run batch analysis via Responses API when available, else Chat Completions."""
    system_msg = (
        "You are a JSON-only response bot for trading "
        "signal analysis. Return ONLY valid JSON, no "
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
        raw_text = await asyncio.wait_for(
            _run_batch_completion(client, prompt, config),
            timeout=config.per_batch_timeout,
        )
        parsed = _parse_json_from_text(raw_text)

        # Attach current_price from input for the reconciler
        price_map = {m.id: m.current_price for m in markets}
        raw_signals = parsed.get("signals", [])
        signals: list[dict] = []
        if isinstance(raw_signals, list):
            for sig in raw_signals:
                if not isinstance(sig, dict):
                    continue
                normalized = dict(sig)
                normalized["current_price"] = price_map.get(
                    normalized.get("market_id")
                )
                signals.append(normalized)

        return BatchResult(
            batch_index=batch_index,
            signals=signals,
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
