"""Polymarket Research Agent – parallel web research powered by GPT-5.1."""

from .agent import ResearchAgent
from .config import AgentConfig, DEFAULT_CONFIG
from .schemas import ResearchInput, ResearchOutput

__all__ = [
    "ResearchAgent",
    "ResearchInput",
    "ResearchOutput",
    "AgentConfig",
    "DEFAULT_CONFIG",
]
