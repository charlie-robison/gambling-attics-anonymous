import asyncio
import json
import logging
from contextlib import asynccontextmanager
from enum import Enum

import chromadb
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from openai import AsyncOpenAI
from pydantic import BaseModel
from py_clob_client.client import ClobClient

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Singletons ---

chroma_client = chromadb.PersistentClient(path="./chroma_data")
collection = chroma_client.get_or_create_collection(
    name="polymarket_markets",
    metadata={"hnsw:space": "cosine"},
)

openai_client = AsyncOpenAI()
clob_client = ClobClient("https://clob.polymarket.com")

GAMMA_API = "https://gamma-api.polymarket.com/markets"
DATA_API = "https://data-api.polymarket.com"
POLL_INTERVAL = 300  # 5 minutes

METADATA_FIELDS = [
    "question", "category", "outcomes", "outcomePrices",
    "volume", "volumeNum", "liquidity", "liquidityNum",
    "endDate", "active", "closed", "slug", "conditionId",
]


# --- Polling ---

async def fetch_and_store_markets():
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
            markets = resp.json()
            if not markets:
                break

            ids = [str(m["id"]) for m in markets]
            existing = collection.get(ids=ids, include=[])
            existing_ids = set(existing["ids"])

            for m in markets:
                mid = str(m["id"])
                if mid in existing_ids or mid in seen_ids:
                    continue
                question = m.get("question", "")
                description = m.get("description", "")
                doc = f"{question} {description}".strip()
                if not doc:
                    continue

                meta = {}
                for field in METADATA_FIELDS:
                    val = m.get(field)
                    if val is not None:
                        # ChromaDB metadata only supports str, int, float, bool
                        if isinstance(val, (str, int, float, bool)):
                            meta[field] = val
                        else:
                            meta[field] = json.dumps(val)

                seen_ids.add(mid)
                all_new_ids.append(mid)
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

        logger.info(f"Added {len(all_new_ids)} markets to ChromaDB (total: {collection.count()})")


async def poll_markets_loop():
    while True:
        try:
            await fetch_and_store_markets()
        except Exception:
            logger.exception("Error polling markets")
        await asyncio.sleep(POLL_INTERVAL)


# --- FastAPI ---


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(poll_markets_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


# --- Models ---

class SearchRequest(BaseModel):
    query: str
    n_results: int = 10


class MarketResult(BaseModel):
    id: str
    question: str | None = None
    category: str | None = None
    outcomes: str | None = None
    outcomePrices: str | None = None
    volume: str | None = None
    volumeNum: float | None = None
    liquidity: str | None = None
    liquidityNum: float | None = None
    endDate: str | None = None
    active: bool | None = None
    closed: bool | None = None
    slug: str | None = None
    conditionId: str | None = None
    relevance_score: float


class SearchResponse(BaseModel):
    results: list[MarketResult]
    expanded_queries: list[str]


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

    # Merge: keep best (lowest) distance per market ID
    best: dict[str, tuple[float, dict]] = {}
    for q_idx in range(len(results["ids"])):
        for i, mid in enumerate(results["ids"][q_idx]):
            dist = results["distances"][q_idx][i]
            meta = results["metadatas"][q_idx][i]
            if mid not in best or dist < best[mid][0]:
                best[mid] = (dist, meta)

    # Sort by distance ascending, take top n
    sorted_results = sorted(best.items(), key=lambda x: x[1][0])[:req.n_results]

    market_results = []
    for mid, (dist, meta) in sorted_results:
        score = 1.0 - (dist / 2.0)
        market_results.append(MarketResult(id=mid, relevance_score=score, **meta))

    return SearchResponse(results=market_results, expanded_queries=expanded)


@app.get("/positions/{user}", response_model=list[Position])
async def get_positions(
    user: str,
    market: str | None = None,
    eventId: str | None = None,
    sizeThreshold: float | None = None,
    redeemable: bool | None = None,
    mergeable: bool | None = None,
    limit: int = Query(default=100, ge=1),
    offset: int = Query(default=0, ge=0),
    sortBy: PositionSortBy | None = None,
    sortDirection: PositionSortDirection | None = None,
):
    params: dict = {"user": user, "limit": limit, "offset": offset}
    if market is not None:
        params["market"] = market
    if eventId is not None:
        params["eventId"] = eventId
    if sizeThreshold is not None:
        params["sizeThreshold"] = sizeThreshold
    if redeemable is not None:
        params["redeemable"] = str(redeemable).lower()
    if mergeable is not None:
        params["mergeable"] = str(mergeable).lower()
    if sortBy is not None:
        params["sortBy"] = sortBy.value
    if sortDirection is not None:
        params["sortDirection"] = sortDirection.value

    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(f"{DATA_API}/positions", params=params)
        resp.raise_for_status()
        positions = resp.json()
        return [p for p in positions if p.get("curPrice", 0) > 0]


@app.get("/")
def health():
    return {"status": "ok"}
