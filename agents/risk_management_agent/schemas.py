"""Pydantic schemas for risk management agent input and output."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SentimentRating(str, Enum):
    """Research sentiment – same values as the research agent."""

    VERY_BEARISH = "very_bearish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    VERY_BULLISH = "very_bullish"


class Prediction(str, Enum):
    """Prediction for whether the event will happen by the market's date."""

    YES = "yes"
    NO = "no"


class ConfidenceLevel(str, Enum):
    """Confidence in the trading signal."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Input schemas — what the MCP actually sends
# ---------------------------------------------------------------------------


class MainEventInfo(BaseModel):
    """Information about the main event being analyzed."""

    title: str = Field(description="Main event title")
    description: Optional[str] = Field(
        default=None,
        description="Optional context about the main event",
    )


class Market(BaseModel):
    """A single prediction market to generate a signal for."""

    id: str = Field(description="Unique market identifier")
    title: str = Field(description="Market question / title")
    current_price: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Current market price (probability) between 0 and 1",
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional resolution criteria or extra context",
    )


class RiskManagementInput(BaseModel):
    """Raw input from the MCP server.

    Contains the full research agent output (as-is) plus the main event
    and markets the user wants trading signals for.  The preprocessor
    will distil ``research_output`` into what the LLM needs.
    """

    research_output: dict[str, Any] = Field(
        description="Full JSON output from the research agent",
    )
    main_event: MainEventInfo = Field(
        description="The main event these markets relate to",
    )
    markets: list[Market] = Field(
        min_length=1,
        description="Prediction markets to generate signals for",
    )


# ---------------------------------------------------------------------------
# Internal schema — what the LLM actually receives (built by preprocessor)
# ---------------------------------------------------------------------------


class RiskAnalysisInput(BaseModel):
    """Preprocessed input fed to the LLM analysis prompts.

    Built automatically from ``RiskManagementInput`` by the preprocessor.
    """

    research_summary: str = Field(
        description="Distilled summary of research findings",
    )
    key_findings: list[str] = Field(
        min_length=1,
        description="Key findings extracted from research",
    )
    sentiment: SentimentRating = Field(
        description="Overall sentiment from research",
    )
    main_event: MainEventInfo = Field(
        description="The main event these markets relate to",
    )
    markets: list[Market] = Field(
        min_length=1,
        description="Prediction markets to analyse and generate signals for",
    )


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------


class MarketSignal(BaseModel):
    """Prediction for a single market."""

    market_id: str = Field(description="Market identifier")
    market_title: str = Field(description="Market question / title")
    prediction: Prediction = Field(
        description="YES = event will happen by this date, NO = it won't",
    )
    confidence: ConfidenceLevel = Field(
        description="Confidence in the prediction",
    )
    rationale: str = Field(
        description="2-4 sentence explanation grounded in research findings",
    )


class RiskAnalysisOutput(BaseModel):
    """Complete risk analysis output with trading signals for every market."""

    event_title: str = Field(description="Main event title")
    signals: list[MarketSignal] = Field(
        description="Predictions – one per input market",
    )
    overall_analysis: str = Field(
        description="2-4 paragraph analysis across all markets",
    )
    timestamp: str = Field(description="ISO 8601 timestamp of analysis")
    disclaimer: str = Field(
        default=(
            "This analysis is for informational purposes only and does not "
            "constitute financial advice. Prediction markets carry significant "
            "risk. Always conduct your own research and never risk more than "
            "you can afford to lose."
        ),
    )
