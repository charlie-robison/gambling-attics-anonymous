import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from enum import Enum

import chromadb
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from openai import AsyncOpenAI
from pydantic import BaseModel
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderType

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

openai_client = AsyncOpenAI()
_private_key = os.environ["PRIVATE_KEY"]
_funder = os.environ["POLYMARKET_WALLET_ADDRESS"]
clob_client = ClobClient(
    "https://clob.polymarket.com",
    chain_id=137,
    key=_private_key,
    signature_type=2,
    funder=_funder,
)
_api_creds = clob_client.create_or_derive_api_creds()
clob_client.set_api_creds(_api_creds)

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
    id: str | None = None
    question: str | None = None
    outcomes: str | None = None
    outcomePrices: str | None = None
    conditionId: str | None = None
    slug: str | None = None
    active: bool | None = None
    closed: bool | None = None
    volume: str | None = None
    liquidity: str | None = None


class EventResult(BaseModel):
    id: str
    title: str | None = None
    category: str | None = None
    slug: str | None = None
    volume: float | None = None
    liquidity: float | None = None
    endDate: str | None = None
    active: bool | None = None
    closed: bool | None = None
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
    asset: str | None = None
    conditionId: str | None = None
    size: float | None = None
    avgPrice: float | None = None
    initialValue: float | None = None
    currentValue: float | None = None
    cashPnl: float | None = None
    percentPnl: float | None = None
    curPrice: float | None = None
    title: str | None = None
    slug: str | None = None
    outcome: str | None = None
    outcomeIndex: int | None = None
    endDate: str | None = None
    market: str | None = None
    eventId: str | None = None
    redeemable: bool | None = None
    mergeable: bool | None = None


# --- Query expansion ---

async def expand_query(query: str) -> list[str]:
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

    results = collection.query(
        query_texts=all_queries,
        n_results=req.n_results,
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
    sorted_results = sorted(best.items(), key=lambda x: x[1][0])[:req.n_results]

    event_results = []
    for eid, (dist, meta) in sorted_results:
        score = 1.0 - (dist / 2.0)
        markets_raw = meta.pop("markets", "[]")
        markets = json.loads(markets_raw)
        event_results.append(
            EventResult(
                id=eid, relevance_score=score,
                markets=[MarketInfo(**m) for m in markets],
                **meta,
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
    sortBy: PositionSortBy | None = None,
    sortDirection: PositionSortDirection | None = None,
):
    user = os.environ["POLYMARKET_WALLET_ADDRESS"]
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
    order_args = MarketOrderArgs(
        token_id=req.token_id,
        amount=req.amount,
        side=req.side.value,
    )
    signed_order = clob_client.create_market_order(order_args)
    return clob_client.post_order(signed_order, OrderType.FOK)


@app.get("/")
def health():
    return {"status": "ok"}
