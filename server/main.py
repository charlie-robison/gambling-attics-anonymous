from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from enum import Enum
from typing import Optional

import chromadb
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from openai import AsyncOpenAI
from pydantic import BaseModel
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderType

try:
    from research_agent import AgentConfig, ResearchAgent, ResearchInput, ResearchOutput
except ImportError:
    from server.research_agent import AgentConfig, ResearchAgent, ResearchInput, ResearchOutput

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Singletons ---

chroma_client = chromadb.PersistentClient(path="./chroma_data")
try:
    chroma_client.delete_collection("polymarket_markets")
except Exception:
    pass

collection = chroma_client.get_or_create_collection(
    name="polymarket_events",
    metadata={"hnsw:space": "cosine"},
)

openai_client: Optional[AsyncOpenAI] = None
_private_key = os.getenv("PRIVATE_KEY")
_funder = os.getenv("POLYMARKET_WALLET_ADDRESS")
clob_trading_enabled = bool(_private_key and _funder)

if clob_trading_enabled:
    clob_client = ClobClient(
        "https://clob.polymarket.com",
        chain_id=137,
        key=_private_key,
        signature_type=2,
        funder=_funder,
    )
    _api_creds = clob_client.create_or_derive_api_creds()
    clob_client.set_api_creds(_api_creds)
else:
    clob_client = ClobClient("https://clob.polymarket.com")
    logger.warning("PRIVATE_KEY and/or POLYMARKET_WALLET_ADDRESS not set; /order disabled")

GAMMA_API = "https://gamma-api.polymarket.com/events"
DATA_API = "https://data-api.polymarket.com"
POLL_INTERVAL = 300  # 5 minutes

METADATA_FIELDS = [
    "title", "category", "slug",
    "volume", "liquidity",
    "endDate", "active", "closed",
]


def _slim_market(m: dict) -> dict:
    return {
        "id": m.get("id"),
        "question": m.get("question"),
        "outcomes": m.get("outcomes"),
        "outcomePrices": m.get("outcomePrices"),
        "conditionId": m.get("conditionId"),
        "slug": m.get("slug"),
        "active": m.get("active"),
        "closed": m.get("closed"),
        "volume": m.get("volume"),
        "liquidity": m.get("liquidity"),
    }


# --- Polling ---

async def fetch_and_store_events():
    async with httpx.AsyncClient(timeout=30) as http:
        offset = 0
        all_new_ids = []
        all_new_docs = []
        all_new_meta = []
        seen_ids = set()

        while True:
            resp = await http.get(
                GAMMA_API,
                params={"limit": 100, "offset": offset, "active": "true", "closed": "false"},
            )
            resp.raise_for_status()
            events = resp.json()
            if not events:
                break

            ids = [str(event["id"]) for event in events]
            existing = collection.get(ids=ids, include=[])
            existing_ids = set(existing["ids"])

            for event in events:
                eid = str(event["id"])
                if eid in existing_ids or eid in seen_ids:
                    continue
                title = event.get("title", "")
                description = event.get("description", "")
                doc = f"{title} {description}".strip()
                if not doc:
                    continue

                meta = {}
                for field in METADATA_FIELDS:
                    val = event.get(field)
                    if val is not None:
                        # ChromaDB metadata only supports str, int, float, bool
                        if isinstance(val, (str, int, float, bool)):
                            meta[field] = val
                        else:
                            meta[field] = json.dumps(val)

                meta["markets"] = json.dumps([_slim_market(m) for m in event.get("markets", [])])

                seen_ids.add(eid)
                all_new_ids.append(eid)
                all_new_docs.append(doc)
                all_new_meta.append(meta)

            offset += 100

        # Batch add in chunks of 500
        for i in range(0, len(all_new_ids), 500):
            collection.add(
                ids=all_new_ids[i:i+500],
                documents=all_new_docs[i:i+500],
                metadatas=all_new_meta[i:i+500],
            )

        logger.info(f"Added {len(all_new_ids)} events to ChromaDB (total: {collection.count()})")


async def poll_events_loop():
    while True:
        try:
            await fetch_and_store_events()
        except Exception:
            logger.exception("Error polling events")
        await asyncio.sleep(POLL_INTERVAL)


# --- FastAPI ---


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(poll_events_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


# --- Models ---

class SearchRequest(BaseModel):
    query: str
    n_results: int = 10


class MarketInfo(BaseModel):
    id: Optional[str] = None
    question: Optional[str] = None
    outcomes: Optional[str] = None
    outcomePrices: Optional[str] = None
    conditionId: Optional[str] = None
    slug: Optional[str] = None
    active: Optional[bool] = None
    closed: Optional[bool] = None
    volume: Optional[str] = None
    liquidity: Optional[str] = None


class EventResult(BaseModel):
    id: str
    title: Optional[str] = None
    category: Optional[str] = None
    slug: Optional[str] = None
    volume: Optional[float] = None
    liquidity: Optional[float] = None
    endDate: Optional[str] = None
    active: Optional[bool] = None
    closed: Optional[bool] = None
    markets: list[MarketInfo] = []
    relevance_score: float


class SearchResponse(BaseModel):
    results: list[EventResult]
    expanded_queries: list[str]


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderRequest(BaseModel):
    token_id: str
    amount: float
    side: OrderSide


class PositionSortBy(str, Enum):
    CURRENT = "CURRENT"
    INITIAL = "INITIAL"
    TOKENS = "TOKENS"
    CASHPNL = "CASHPNL"
    PERCENTPNL = "PERCENTPNL"
    TITLE = "TITLE"
    RESOLVING = "RESOLVING"
    PRICE = "PRICE"
    AVGPRICE = "AVGPRICE"


class PositionSortDirection(str, Enum):
    ASC = "ASC"
    DESC = "DESC"


class Position(BaseModel):
    asset: Optional[str] = None
    conditionId: Optional[str] = None
    size: Optional[float] = None
    avgPrice: Optional[float] = None
    initialValue: Optional[float] = None
    currentValue: Optional[float] = None
    cashPnl: Optional[float] = None
    percentPnl: Optional[float] = None
    curPrice: Optional[float] = None
    title: Optional[str] = None
    slug: Optional[str] = None
    outcome: Optional[str] = None
    outcomeIndex: Optional[int] = None
    endDate: Optional[str] = None
    market: Optional[str] = None
    eventId: Optional[str] = None
    redeemable: Optional[bool] = None
    mergeable: Optional[bool] = None


# --- Query expansion ---

async def expand_query(query: str) -> list[str]:
    global openai_client

    if openai_client is None:
        try:
            openai_client = AsyncOpenAI()
        except Exception:
            logger.exception("OpenAI client initialization failed; skipping query expansion")
            return []

    try:
        resp = await openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate 3-5 related search terms for finding prediction markets. "
                        "Return JSON: {\"terms\": [\"term1\", \"term2\", ...]}"
                    ),
                },
                {"role": "user", "content": query},
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        return data.get("terms", [])
    except Exception:
        logger.exception("Query expansion failed")
        return []


# --- Endpoints ---

@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    expanded = await expand_query(req.query)
    all_queries = [req.query] + expanded
    total_events = collection.count()
    n_results = max(1, req.n_results)

    if total_events == 0:
        return SearchResponse(results=[], expanded_queries=expanded)

    n_results = min(n_results, total_events)

    results = collection.query(
        query_texts=all_queries,
        n_results=n_results,
        include=["metadatas", "distances"],
    )

    # Merge: keep best (lowest) distance per event ID
    best: dict[str, tuple[float, dict]] = {}
    for q_idx in range(len(results["ids"])):
        for i, eid in enumerate(results["ids"][q_idx]):
            dist = results["distances"][q_idx][i]
            meta = results["metadatas"][q_idx][i]
            if eid not in best or dist < best[eid][0]:
                best[eid] = (dist, meta)

    # Sort by distance ascending, take top n
    sorted_results = sorted(best.items(), key=lambda x: x[1][0])[:n_results]

    event_results = []
    for eid, (dist, meta) in sorted_results:
        score = 1.0 - (dist / 2.0)
        meta_safe = dict(meta or {})
        markets_raw = meta_safe.pop("markets", "[]")
        try:
            markets = json.loads(markets_raw) if isinstance(markets_raw, str) else []
        except json.JSONDecodeError:
            markets = []
        event_results.append(
            EventResult(
                id=eid, relevance_score=score,
                markets=[MarketInfo(**m) for m in markets],
                **meta_safe,
            )
        )

    return SearchResponse(results=event_results, expanded_queries=expanded)


@app.get("/positions", response_model=list[Position])
async def get_positions(
    market: str | None = None,
    eventId: str | None = None,
    sizeThreshold: float | None = None,
    limit: int = Query(default=100, ge=1),
    offset: int = Query(default=0, ge=0),
    sortBy: Optional[PositionSortBy] = None,
    sortDirection: Optional[PositionSortDirection] = None,
):
    user = os.getenv("POLYMARKET_WALLET_ADDRESS")
    if not user:
        raise HTTPException(status_code=500, detail="POLYMARKET_WALLET_ADDRESS is not configured")
    params: dict = {"user": user, "limit": limit, "offset": offset}
    if market is not None:
        params["market"] = market
    if eventId is not None:
        params["eventId"] = eventId
    if sizeThreshold is not None:
        params["sizeThreshold"] = sizeThreshold
    if sortBy is not None:
        params["sortBy"] = sortBy.value
    if sortDirection is not None:
        params["sortDirection"] = sortDirection.value

    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(f"{DATA_API}/positions", params=params)
        resp.raise_for_status()
        positions = resp.json()
        return [
            p for p in positions
            if p.get("curPrice", 0) > 0
            and not p.get("redeemable")
            and not p.get("mergeable")
        ]


@app.post("/order")
def place_order(req: OrderRequest):
    if not clob_trading_enabled:
        raise HTTPException(
            status_code=500,
            detail="Trading is not configured. Set PRIVATE_KEY and POLYMARKET_WALLET_ADDRESS.",
        )
    order_args = MarketOrderArgs(
        token_id=req.token_id,
        amount=req.amount,
        side=req.side.value,
    )
    signed_order = clob_client.create_market_order(order_args)
    return clob_client.post_order(signed_order, OrderType.FOK)


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/research", response_model=ResearchOutput)
async def research(
    body: ResearchInput,
    model: str = Query("gpt-5.1", description="OpenAI model to use"),
    timeout: float = Query(180.0, description="Total pipeline timeout in seconds"),
) -> ResearchOutput:
    config = AgentConfig(model=model, total_timeout=timeout)
    agent = ResearchAgent(config=config)
    return await agent.run(body)
