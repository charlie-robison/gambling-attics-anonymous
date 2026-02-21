"""Configuration for the Polymarket research agent."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    """Immutable configuration for the research agent."""

    # Model
    model: str = "gpt-5.1"

    # Web search
    search_context_size: str = "high"  # "low" | "medium" | "high"

    # Timeouts (seconds)
    per_research_timeout: float = 90.0   # Per individual research call
    synthesis_timeout: float = 60.0      # Synthesis LLM call
    total_timeout: float = 180.0         # Hard ceiling for entire pipeline

    # Concurrency
    max_concurrent_research: int = 10

    # Retries
    max_retries: int = 2
    retry_delay: float = 1.0

    # Output limits
    max_news_links_per_event: int = 8
    max_key_findings_per_event: int = 7


DEFAULT_CONFIG = AgentConfig()
