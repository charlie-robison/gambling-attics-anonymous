"""Pydantic schemas for research agent input and output."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Input schemas – intentionally minimal. The research agent only needs to
# know *what* to research (title + description).
# ---------------------------------------------------------------------------


class MainEvent(BaseModel):
    """The parent event that groups related sub-events together."""

    title: str = Field(description="Event title, e.g. '2028 US Presidential Election'")
    description: Optional[str] = Field(
        default=None, description="Optional longer description of the event"
    )


class SubEvent(BaseModel):
    """A single sub-event / market question to research."""

    id: str = Field(description="Unique identifier for this sub-event")
    title: str = Field(
        description="The specific question, e.g. 'Will X happen by Y date?'"
    )
    description: Optional[str] = Field(
        default=None, description="Optional longer description or resolution criteria"
    )


class ResearchInput(BaseModel):
    """Top-level input to the research agent.

    Either ``main_event`` + ``sub_events``, or just ``sub_events`` alone.
    """

    main_event: Optional[MainEvent] = Field(
        default=None,
        description="The parent event. If None, sub_events are treated independently.",
    )
    sub_events: list[SubEvent] = Field(
        min_length=1,
        description="One or more sub-events / market questions to research.",
    )


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------


class SentimentRating(str, Enum):
    VERY_BEARISH = "very_bearish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    VERY_BULLISH = "very_bullish"


class NewsLink(BaseModel):
    """A single news source discovered during research."""

    title: str = Field(description="Article or source title")
    url: str = Field(description="Direct URL to the source")
    snippet: Optional[str] = Field(
        default=None, description="Brief relevant excerpt or description"
    )
    published_date: Optional[str] = Field(
        default=None, description="Publication date if available"
    )
    source_name: Optional[str] = Field(
        default=None, description="Publisher name, e.g. 'Reuters'"
    )


class MainEventResearch(BaseModel):
    """Research results for the main / parent event."""

    event_title: str
    summary: str = Field(
        description="1-2 page research summary with key findings and context"
    )
    key_findings: list[str] = Field(description="3-7 bullet-point key findings")
    news_links: list[NewsLink] = Field(description="Relevant news sources found")
    sentiment: SentimentRating
    sentiment_rationale: str = Field(
        description="1-2 sentence explanation of sentiment rating"
    )


class SubEventResearch(BaseModel):
    """Research results for a single sub-event / market question."""

    sub_event_id: str
    sub_event_title: str
    summary: str = Field(
        description="1-2 page research summary with key findings"
    )
    key_findings: list[str] = Field(description="3-7 bullet-point key findings")
    news_links: list[NewsLink] = Field(description="Relevant news sources found")
    sentiment: SentimentRating
    sentiment_rationale: str = Field(
        description="1-2 sentence explanation of sentiment rating"
    )


class SubEventRelationship(BaseModel):
    """How a sub-event relates to and could influence the main event."""

    sub_event_id: str
    sub_event_title: str
    relationship_summary: str = Field(
        description="How this sub-event connects to the main event"
    )
    influencing_news: str = Field(
        description=(
            "What specific news or developments around this sub-event "
            "could influence the main event, and how"
        )
    )


class ResearchOutput(BaseModel):
    """Complete research output returned to the MCP server."""

    main_event_research: Optional[MainEventResearch] = Field(
        default=None,
        description="Research on the main event. None if no main_event was provided.",
    )
    sub_event_research: list[SubEventResearch] = Field(
        description="Research results for each sub-event"
    )
    relationships: Optional[list[SubEventRelationship]] = Field(
        default=None,
        description="How sub-events relate to main event. None if no main_event.",
    )
    synthesis: str = Field(
        description="Overall synthesis combining all research into a coherent narrative"
    )
    research_timestamp: str = Field(
        description="ISO 8601 timestamp of when this research was conducted"
    )
    disclaimer: str = Field(
        default=(
            "This research is for informational purposes only and does not "
            "constitute financial advice. Prediction markets carry risk. "
            "Always do your own research before making any decisions."
        ),
    )
