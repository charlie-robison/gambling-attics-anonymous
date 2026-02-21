"""Individual event research using GPT-5.1 with web_search_preview.

Each public function performs a single research task and returns a
``RawResearchResult`` containing the full research text plus extracted
source links.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Callable, Coroutine

from openai import AsyncOpenAI

from .config import AgentConfig, DEFAULT_CONFIG
from .prompts import MAIN_EVENT_RESEARCH_PROMPT, SUB_EVENT_RESEARCH_PROMPT
from .schemas import MainEvent, NewsLink, SubEvent


# ---------------------------------------------------------------------------
# Data container for a single research call's output
# ---------------------------------------------------------------------------


@dataclass
class RawResearchResult:
    """Raw output from a single web-search research call."""

    event_id: str
    event_title: str
    research_text: str  # Full text from GPT with inline citations
    news_links: list[NewsLink] = field(default_factory=list)
    is_main_event: bool = False
    error: str | None = None


# ---------------------------------------------------------------------------
# Citation extraction helpers
# ---------------------------------------------------------------------------


def _extract_news_links(response: object) -> list[NewsLink]:
    """Extract ``NewsLink`` objects from OpenAI response annotations.

    The Responses API returns output items; ``message`` items contain
    ``content`` blocks that may carry ``url_citation`` annotations.
    """
    links: list[NewsLink] = []
    seen_urls: set[str] = set()

    for item in response.output:  # type: ignore[attr-defined]
        if getattr(item, "type", None) != "message":
            continue
        for block in getattr(item, "content", []):
            for annotation in getattr(block, "annotations", []):
                url = getattr(annotation, "url", None)
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    links.append(
                        NewsLink(
                            title=getattr(annotation, "title", "") or "",
                            url=url,
                        )
                    )
    return links


# ---------------------------------------------------------------------------
# Research functions
# ---------------------------------------------------------------------------


async def research_main_event(
    client: AsyncOpenAI,
    event: MainEvent,
    config: AgentConfig = DEFAULT_CONFIG,
) -> RawResearchResult:
    """Research a main event using agentic web search."""

    prompt = MAIN_EVENT_RESEARCH_PROMPT.format(
        title=event.title,
        description=event.description or "No additional description provided.",
    )

    try:
        response = await asyncio.wait_for(
            client.responses.create(
                model=config.model,
                tools=[
                    {
                        "type": "web_search_preview",
                        "search_context_size": config.search_context_size,
                    }
                ],
                input=prompt,
            ),
            timeout=config.per_research_timeout,
        )

        return RawResearchResult(
            event_id="main",
            event_title=event.title,
            research_text=response.output_text,
            news_links=_extract_news_links(response)[
                : config.max_news_links_per_event
            ],
            is_main_event=True,
        )

    except asyncio.TimeoutError:
        return RawResearchResult(
            event_id="main",
            event_title=event.title,
            research_text="",
            is_main_event=True,
            error=f"Research timed out after {config.per_research_timeout}s",
        )
    except Exception as exc:
        return RawResearchResult(
            event_id="main",
            event_title=event.title,
            research_text="",
            is_main_event=True,
            error=f"Research failed: {exc}",
        )


async def research_sub_event(
    client: AsyncOpenAI,
    sub_event: SubEvent,
    config: AgentConfig = DEFAULT_CONFIG,
) -> RawResearchResult:
    """Research a single sub-event / market question using agentic web search."""

    prompt = SUB_EVENT_RESEARCH_PROMPT.format(
        title=sub_event.title,
        description=sub_event.description or "No additional description provided.",
    )

    try:
        response = await asyncio.wait_for(
            client.responses.create(
                model=config.model,
                tools=[
                    {
                        "type": "web_search_preview",
                        "search_context_size": config.search_context_size,
                    }
                ],
                input=prompt,
            ),
            timeout=config.per_research_timeout,
        )

        return RawResearchResult(
            event_id=sub_event.id,
            event_title=sub_event.title,
            research_text=response.output_text,
            news_links=_extract_news_links(response)[
                : config.max_news_links_per_event
            ],
            is_main_event=False,
        )

    except asyncio.TimeoutError:
        return RawResearchResult(
            event_id=sub_event.id,
            event_title=sub_event.title,
            research_text="",
            is_main_event=False,
            error=f"Research timed out after {config.per_research_timeout}s",
        )
    except Exception as exc:
        return RawResearchResult(
            event_id=sub_event.id,
            event_title=sub_event.title,
            research_text="",
            is_main_event=False,
            error=f"Research failed: {exc}",
        )


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------


async def research_with_retry(
    coro_factory: Callable[[], Coroutine[None, None, RawResearchResult]],
    config: AgentConfig = DEFAULT_CONFIG,
) -> RawResearchResult:
    """Retry a research call up to ``config.max_retries`` times on failure."""

    last_result: RawResearchResult | None = None
    for attempt in range(1 + config.max_retries):
        result = await coro_factory()
        if result.error is None:
            return result
        last_result = result
        if attempt < config.max_retries:
            await asyncio.sleep(config.retry_delay)
    return last_result  # type: ignore[return-value]
