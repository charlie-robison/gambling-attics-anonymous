"""Configuration for the risk management agent."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskAgentConfig:
    """Immutable configuration for the risk management agent.

    Follows the same frozen-dataclass pattern as the research agent.
    """

    # Model
    model: str = "gpt-5.1"

    # Batching
    batch_size: int = 5  # markets per parallel LLM call
    max_concurrent_batches: int = 10  # asyncio semaphore limit

    # Timeouts (seconds)
    per_batch_timeout: float = 45.0  # individual batch LLM call
    reconciliation_timeout: float = 30.0  # reconciliation LLM call
    total_timeout: float = 90.0  # hard ceiling for entire pipeline

    # Retries
    max_retries: int = 2
    retry_delay: float = 1.0


DEFAULT_RISK_CONFIG = RiskAgentConfig()
