"""RiskManagementAgent – orchestrator for the parallel batch analysis pipeline.

Stage 0: Preprocess raw MCP payload into compact LLM-ready input (pure Python)
Stage 1: Split markets into batches, analyse each in parallel (LLM calls)
Stage 2: Reconcile all predictions for cross-market consistency (LLM call)
Stage 3: Assemble structured output (pure Python)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from openai import AsyncOpenAI

from .analyzer import (
    BatchResult,
    analyze_batch,
    analyze_batch_with_retry,
    build_fallback_batch,
)
from .config import DEFAULT_RISK_CONFIG, RiskAgentConfig
from .preprocessor import preprocess
from .reconciler import (
    ReconciliationResult,
    build_fallback_reconciliation,
    reconcile_signals,
    reconcile_with_retry,
)
from .schemas import (
    ConfidenceLevel,
    Market,
    MarketSignal,
    Prediction,
    RiskAnalysisInput,
    RiskAnalysisOutput,
    RiskManagementInput,
)


class RiskManagementAgent:
    """Prediction market risk management agent.

    Usage::

        agent = RiskManagementAgent()
        result = await agent.run(risk_input)
        print(result.model_dump_json(indent=2))
    """

    def __init__(
        self,
        config: RiskAgentConfig = DEFAULT_RISK_CONFIG,
        api_key: str | None = None,
    ) -> None:
        self.config = config
        self.client = AsyncOpenAI(api_key=api_key) if api_key else AsyncOpenAI()

    async def run(self, raw_input: RiskManagementInput) -> RiskAnalysisOutput:
        """Execute the risk analysis pipeline.

        1. Preprocess the raw MCP payload (pure Python, instant).
        2. Run parallel batch analysis + reconciliation (LLM calls).
        3. Assemble structured output.
        """

        # ── Stage 0: Preprocess ──────────────────────────────────────
        input_data = preprocess(raw_input)

        try:
            return await asyncio.wait_for(
                self._run_pipeline(input_data),
                timeout=self.config.total_timeout,
            )
        except asyncio.TimeoutError:
            # Emergency fallback – all NO
            fallback_signals = []
            for m in input_data.markets:
                fallback_signals.append(
                    {
                        "market_id": m.id,
                        "market_title": m.title,
                        "prediction": "no",
                        "confidence": "low",
                        "rationale": (
                            f"Pipeline timed out after "
                            f"{self.config.total_timeout}s. "
                            "Defaulting to NO."
                        ),
                    }
                )
            return self._assemble_output(
                input_data=input_data,
                final_signals=fallback_signals,
                overall_analysis=(
                    f"Analysis timed out after "
                    f"{self.config.total_timeout}s. All predictions default to "
                    "NO with low confidence. Manual review required."
                ),
            )

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    async def _run_pipeline(
        self, input_data: RiskAnalysisInput
    ) -> RiskAnalysisOutput:
        """Stage 1 → Stage 2 → Stage 3."""

        # ── Stage 1: Parallel batch analysis ─────────────────────────
        batches = _split_into_batches(input_data.markets, self.config.batch_size)
        semaphore = asyncio.Semaphore(self.config.max_concurrent_batches)

        tasks: list[tuple[int, list[Market], asyncio.Task[BatchResult]]] = []
        for idx, batch_markets in enumerate(batches):
            bm = batch_markets  # capture for closure
            bi = idx

            async def _run_batch(
                bm: list[Market] = bm, bi: int = bi
            ) -> BatchResult:
                async with semaphore:
                    return await analyze_batch_with_retry(
                        lambda bm=bm, bi=bi: analyze_batch(
                            self.client,
                            input_data,
                            bm,
                            bi,
                            self.config,
                        ),
                        self.config,
                    )

            task = asyncio.create_task(_run_batch())
            tasks.append((idx, batch_markets, task))

        # Wait for all batches
        await asyncio.gather(
            *(t for _, _, t in tasks), return_exceptions=True
        )

        # Collect signals from all batches
        all_signals: list[dict] = []
        for idx, batch_markets, task in tasks:
            try:
                result = task.result()
            except Exception as exc:
                result = build_fallback_batch(
                    batch_markets, idx, str(exc)
                )

            if result.success:
                all_signals.extend(result.signals)
            else:
                fallback = build_fallback_batch(
                    batch_markets, idx, result.error or "unknown error"
                )
                all_signals.extend(fallback.signals)

        # ── Stage 2: Reconciliation ──────────────────────────────────
        recon_result: ReconciliationResult = await reconcile_with_retry(
            lambda: reconcile_signals(
                client=self.client,
                main_event_title=input_data.main_event.title,
                main_event_description=input_data.main_event.description,
                sentiment=input_data.sentiment.value,
                all_signals=all_signals,
                config=self.config,
            ),
            self.config,
        )

        if not recon_result.success:
            recon_result = build_fallback_reconciliation(
                all_signals=all_signals,
                sentiment=input_data.sentiment.value,
                error_msg=recon_result.error or "unknown error",
            )

        # ── Stage 3: Assemble output ─────────────────────────────────
        return self._assemble_output(
            input_data=input_data,
            final_signals=recon_result.signals,
            overall_analysis=recon_result.overall_analysis,
        )

    # ------------------------------------------------------------------
    # Output assembly
    # ------------------------------------------------------------------

    def _assemble_output(
        self,
        input_data: RiskAnalysisInput,
        final_signals: list[dict],
        overall_analysis: str,
    ) -> RiskAnalysisOutput:
        """Map reconciled predictions onto Pydantic output models."""

        signals: list[MarketSignal] = []
        for s in final_signals:
            signals.append(
                MarketSignal(
                    market_id=s.get("market_id", ""),
                    market_title=s.get("market_title", ""),
                    prediction=_parse_prediction(
                        s.get("prediction", "no")
                    ),
                    confidence=_parse_confidence(
                        s.get("confidence", "low")
                    ),
                    rationale=s.get("rationale", "No rationale provided."),
                )
            )

        return RiskAnalysisOutput(
            event_title=input_data.main_event.title,
            signals=signals,
            overall_analysis=overall_analysis or "Analysis unavailable.",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _split_into_batches(
    markets: list[Market], batch_size: int
) -> list[list[Market]]:
    """Split a flat list of markets into batches."""
    return [
        markets[i : i + batch_size]
        for i in range(0, len(markets), batch_size)
    ]


def _parse_prediction(value: str) -> Prediction:
    """Safely parse a prediction string into the enum."""
    try:
        return Prediction(value.lower().strip())
    except ValueError:
        return Prediction.NO


def _parse_confidence(value: str) -> ConfidenceLevel:
    """Safely parse a confidence string into the enum."""
    try:
        return ConfidenceLevel(value.lower().strip())
    except ValueError:
        return ConfidenceLevel.LOW
