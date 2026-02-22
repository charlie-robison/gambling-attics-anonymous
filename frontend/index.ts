import { MCPServer, object, text, widget } from "mcp-use/server";
import { z } from "zod";

const server = new MCPServer({
  name: "gambling-attics-anonymous",
  title: "gambling-attics-anonymous",
  version: "1.0.0",
  description: "MCP server with MCP Apps integration",
  baseUrl: process.env.MCP_URL || "http://localhost:3000",
  favicon: "favicon.ico",
  websiteUrl: "https://mcp-use.com",
  icons: [
    {
      src: "icon.svg",
      mimeType: "image/svg+xml",
      sizes: ["512x512"],
    },
  ],
});

// ─── Mock positions data ───────────────────────────────────────────────────────

const positions = [
  { id: "pos-1", marketTitle: "Will Bitcoin reach $100k by end of 2026?", outcome: "Yes", shares: 150, avgPrice: 0.62, currentPrice: 0.74, pnl: 18.0, pnlPercent: 19.35, marketSlug: "bitcoin-100k-2026" },
  { id: "pos-2", marketTitle: "US Presidential Election 2028 - Democrat wins?", outcome: "No", shares: 200, avgPrice: 0.45, currentPrice: 0.38, pnl: -14.0, pnlPercent: -15.56, marketSlug: "us-presidential-2028-democrat" },
  { id: "pos-3", marketTitle: "Will SpaceX land humans on Mars by 2030?", outcome: "Yes", shares: 75, avgPrice: 0.18, currentPrice: 0.22, pnl: 3.0, pnlPercent: 22.22, marketSlug: "spacex-mars-2030" },
  { id: "pos-4", marketTitle: "Fed rate cut before July 2026?", outcome: "Yes", shares: 500, avgPrice: 0.71, currentPrice: 0.83, pnl: 60.0, pnlPercent: 16.9, marketSlug: "fed-rate-cut-july-2026" },
  { id: "pos-5", marketTitle: "Will AI pass the Turing Test by 2027?", outcome: "No", shares: 100, avgPrice: 0.55, currentPrice: 0.60, pnl: -5.0, pnlPercent: -9.09, marketSlug: "ai-turing-test-2027" },
];

// ─── Mock market data (used for event market typing) ───────────────────────────

const markets = [
  { id: "mkt-1", title: "Who will Trump nominate as Fed Chair?", slug: "trump-fed-chair", category: "Politics", volume: 184018881, liquidity: 1250000, endDate: "2026-12-31T23:59:59Z", outcomes: [{ name: "Kevin Warsh", price: 0.93 }, { name: "Judy Shelton", price: 0.04 }], isResolved: false, subMarketCount: 23 },
  { id: "mkt-2", title: "2028 U.S. Presidential Election winner?", slug: "us-presidential-2028", category: "Politics", volume: 13350423, liquidity: 920000, endDate: "2028-11-05T23:59:59Z", outcomes: [{ name: "J.D. Vance", price: 0.23 }, { name: "Gavin Newsom", price: 0.19 }], isResolved: false, subMarketCount: 24 },
  { id: "mkt-3", title: "When will Bitcoin hit $150k?", slug: "bitcoin-150k", category: "Crypto", volume: 26896828, liquidity: 480000, endDate: "2027-12-31T23:59:59Z", outcomes: [{ name: "Before June 2026", price: 0.05 }, { name: "Before May 2026", price: 0.03 }], isResolved: false, subMarketCount: 4 },
  { id: "mkt-4", title: "Fed rate cut before July 2026?", slug: "fed-rate-cut-july-2026", category: "Economics", volume: 38601209, liquidity: 290000, endDate: "2026-07-01T23:59:59Z", outcomes: [{ name: "Yes", price: 0.83 }, { name: "No", price: 0.17 }], isResolved: false },
  { id: "mkt-5", title: "Will AI pass the Turing Test by 2027?", slug: "ai-turing-test-2027", category: "Science", volume: 1750000, liquidity: 140000, endDate: "2027-12-31T23:59:59Z", outcomes: [{ name: "Yes", price: 0.40 }, { name: "No", price: 0.60 }], isResolved: false },
  { id: "mkt-6", title: "Champions League 2026 winner?", slug: "champions-league-2026", category: "Sports", volume: 38601209, liquidity: 410000, endDate: "2026-06-01T23:59:59Z", outcomes: [{ name: "Real Madrid", price: 0.32 }, { name: "Arsenal", price: 0.16 }], isResolved: false, subMarketCount: 51 },
  { id: "mkt-7", title: "Will Ethereum flip Bitcoin market cap by 2027?", slug: "eth-flip-btc-2027", category: "Crypto", volume: 980000, liquidity: 72000, endDate: "2027-12-31T23:59:59Z", outcomes: [{ name: "Yes", price: 0.09 }, { name: "No", price: 0.91 }], isResolved: false },
  { id: "mkt-8", title: "US GDP growth above 3% in 2026?", slug: "us-gdp-growth-2026", category: "Economics", volume: 2100000, liquidity: 165000, endDate: "2027-01-31T23:59:59Z", outcomes: [{ name: "Yes", price: 0.55 }, { name: "No", price: 0.45 }], isResolved: false },
];

// ─── Mock events data (groups markets under events) ────────────────────────────

type MarketData = typeof markets[number];

interface EventData {
  id: string;
  title: string;
  description: string;
  slug: string;
  category: string;
  volume: number;
  markets: MarketData[];
}

const events: EventData[] = [
  {
    id: "evt-1",
    title: "2028 US Presidential Election",
    description: "The 2028 United States presidential election is shaping up to be one of the most competitive races in recent history. Markets are tracking potential candidates across both parties, including J.D. Vance, Gavin Newsom, and several dark horse candidates.",
    slug: "us-presidential-2028",
    category: "Politics",
    volume: 42_500_000,
    markets: [
      { id: "mkt-2", title: "2028 U.S. Presidential Election winner?", slug: "us-presidential-2028", category: "Politics", volume: 13350423, liquidity: 920000, endDate: "2028-11-05T23:59:59Z", outcomes: [{ name: "J.D. Vance", price: 0.23 }, { name: "Gavin Newsom", price: 0.19 }], isResolved: false, subMarketCount: 24 },
      { id: "mkt-9", title: "Will a Democrat win the 2028 presidency?", slug: "us-presidential-2028-democrat", category: "Politics", volume: 8200000, liquidity: 620000, endDate: "2028-11-05T23:59:59Z", outcomes: [{ name: "Yes", price: 0.42 }, { name: "No", price: 0.58 }], isResolved: false },
      { id: "mkt-10", title: "Will J.D. Vance be the Republican nominee?", slug: "jd-vance-gop-nominee-2028", category: "Politics", volume: 5600000, liquidity: 340000, endDate: "2028-08-01T23:59:59Z", outcomes: [{ name: "Yes", price: 0.55 }, { name: "No", price: 0.45 }], isResolved: false },
      { id: "mkt-11", title: "Third-party candidate gets 5%+ in 2028?", slug: "third-party-5pct-2028", category: "Politics", volume: 1200000, liquidity: 95000, endDate: "2028-11-05T23:59:59Z", outcomes: [{ name: "Yes", price: 0.12 }, { name: "No", price: 0.88 }], isResolved: false },
      { id: "mkt-12", title: "2028 popular vote winner?", slug: "popular-vote-2028", category: "Politics", volume: 3400000, liquidity: 210000, endDate: "2028-11-05T23:59:59Z", outcomes: [{ name: "Democrat", price: 0.54 }, { name: "Republican", price: 0.46 }], isResolved: false },
    ],
  },
  {
    id: "evt-2",
    title: "Crypto Price Milestones",
    description: "Cryptocurrency markets remain volatile with Bitcoin eyeing new all-time highs. Traders are betting on whether BTC will reach $150k or $200k, and whether Ethereum can close the gap on Bitcoin's market cap dominance.",
    slug: "crypto-price-milestones",
    category: "Crypto",
    volume: 35_800_000,
    markets: [
      { id: "mkt-3", title: "When will Bitcoin hit $150k?", slug: "bitcoin-150k", category: "Crypto", volume: 26896828, liquidity: 480000, endDate: "2027-12-31T23:59:59Z", outcomes: [{ name: "Before June 2026", price: 0.05 }, { name: "Before May 2026", price: 0.03 }], isResolved: false, subMarketCount: 4 },
      { id: "mkt-7", title: "Will Ethereum flip Bitcoin market cap by 2027?", slug: "eth-flip-btc-2027", category: "Crypto", volume: 980000, liquidity: 72000, endDate: "2027-12-31T23:59:59Z", outcomes: [{ name: "Yes", price: 0.09 }, { name: "No", price: 0.91 }], isResolved: false },
      { id: "mkt-13", title: "Will Bitcoin hit $200k by 2028?", slug: "bitcoin-200k-2028", category: "Crypto", volume: 4500000, liquidity: 310000, endDate: "2028-12-31T23:59:59Z", outcomes: [{ name: "Yes", price: 0.18 }, { name: "No", price: 0.82 }], isResolved: false },
      { id: "mkt-14", title: "Solana above $500 by end of 2027?", slug: "solana-500-2027", category: "Crypto", volume: 2100000, liquidity: 150000, endDate: "2027-12-31T23:59:59Z", outcomes: [{ name: "Yes", price: 0.15 }, { name: "No", price: 0.85 }], isResolved: false },
    ],
  },
  {
    id: "evt-3",
    title: "US Federal Reserve Policy 2026",
    description: "The Federal Reserve's monetary policy decisions in 2026 are being closely watched by markets. Key questions include the timing and magnitude of rate cuts, the next Fed Chair nomination, and overall economic growth trajectory.",
    slug: "fed-policy-2026",
    category: "Economics",
    volume: 225_000_000,
    markets: [
      { id: "mkt-1", title: "Who will Trump nominate as Fed Chair?", slug: "trump-fed-chair", category: "Economics", volume: 184018881, liquidity: 1250000, endDate: "2026-12-31T23:59:59Z", outcomes: [{ name: "Kevin Warsh", price: 0.93 }, { name: "Judy Shelton", price: 0.04 }], isResolved: false, subMarketCount: 23 },
      { id: "mkt-4", title: "Fed rate cut before July 2026?", slug: "fed-rate-cut-july-2026", category: "Economics", volume: 38601209, liquidity: 290000, endDate: "2026-07-01T23:59:59Z", outcomes: [{ name: "Yes", price: 0.83 }, { name: "No", price: 0.17 }], isResolved: false },
      { id: "mkt-8", title: "US GDP growth above 3% in 2026?", slug: "us-gdp-growth-2026", category: "Economics", volume: 2100000, liquidity: 165000, endDate: "2027-01-31T23:59:59Z", outcomes: [{ name: "Yes", price: 0.55 }, { name: "No", price: 0.45 }], isResolved: false },
      { id: "mkt-15", title: "Fed funds rate below 3% by end of 2026?", slug: "fed-funds-below-3-2026", category: "Economics", volume: 1800000, liquidity: 120000, endDate: "2026-12-31T23:59:59Z", outcomes: [{ name: "Yes", price: 0.35 }, { name: "No", price: 0.65 }], isResolved: false },
    ],
  },
  {
    id: "evt-4",
    title: "AI & Technology Milestones",
    description: "Artificial intelligence is advancing rapidly, with major milestones being tracked across prediction markets. From passing the Turing Test to achieving AGI, these markets capture the collective wisdom on AI's trajectory.",
    slug: "ai-tech-milestones",
    category: "Science",
    volume: 12_500_000,
    markets: [
      { id: "mkt-5", title: "Will AI pass the Turing Test by 2027?", slug: "ai-turing-test-2027", category: "Science", volume: 1750000, liquidity: 140000, endDate: "2027-12-31T23:59:59Z", outcomes: [{ name: "Yes", price: 0.40 }, { name: "No", price: 0.60 }], isResolved: false },
      { id: "mkt-16", title: "AGI achieved by 2030?", slug: "agi-by-2030", category: "Science", volume: 5200000, liquidity: 380000, endDate: "2030-12-31T23:59:59Z", outcomes: [{ name: "Yes", price: 0.22 }, { name: "No", price: 0.78 }], isResolved: false },
      { id: "mkt-17", title: "AI replaces 50% of coding jobs by 2028?", slug: "ai-coding-jobs-2028", category: "Science", volume: 3100000, liquidity: 220000, endDate: "2028-12-31T23:59:59Z", outcomes: [{ name: "Yes", price: 0.08 }, { name: "No", price: 0.92 }], isResolved: false },
      { id: "mkt-18", title: "First AI-authored bestseller by 2027?", slug: "ai-bestseller-2027", category: "Science", volume: 890000, liquidity: 65000, endDate: "2027-12-31T23:59:59Z", outcomes: [{ name: "Yes", price: 0.14 }, { name: "No", price: 0.86 }], isResolved: false },
    ],
  },
  {
    id: "evt-5",
    title: "Champions League & European Football",
    description: "European football's premier club competition continues to captivate fans and bettors worldwide. With Real Madrid as the defending champions and Arsenal surging, the 2025-26 season promises intense competition.",
    slug: "champions-league-football",
    category: "Sports",
    volume: 48_000_000,
    markets: [
      { id: "mkt-6", title: "Champions League 2026 winner?", slug: "champions-league-2026", category: "Sports", volume: 38601209, liquidity: 410000, endDate: "2026-06-01T23:59:59Z", outcomes: [{ name: "Real Madrid", price: 0.32 }, { name: "Arsenal", price: 0.16 }], isResolved: false, subMarketCount: 51 },
      { id: "mkt-19", title: "Will Real Madrid win La Liga 2026?", slug: "real-madrid-la-liga-2026", category: "Sports", volume: 4200000, liquidity: 280000, endDate: "2026-06-01T23:59:59Z", outcomes: [{ name: "Yes", price: 0.45 }, { name: "No", price: 0.55 }], isResolved: false },
      { id: "mkt-20", title: "Premier League champion 2025-26?", slug: "premier-league-2026", category: "Sports", volume: 6800000, liquidity: 450000, endDate: "2026-05-25T23:59:59Z", outcomes: [{ name: "Arsenal", price: 0.38 }, { name: "Man City", price: 0.28 }], isResolved: false, subMarketCount: 20 },
      { id: "mkt-21", title: "Ballon d'Or 2026 winner?", slug: "ballon-dor-2026", category: "Sports", volume: 2300000, liquidity: 170000, endDate: "2026-10-15T23:59:59Z", outcomes: [{ name: "Vinicius Jr", price: 0.30 }, { name: "Bellingham", price: 0.22 }], isResolved: false, subMarketCount: 15 },
    ],
  },
];

const incomingMarketSchema = z.object({
  id: z.string().optional(),
  title: z.string().nullable().optional(),
  question: z.string().nullable().optional(),
  slug: z.string().nullable().optional(),
  category: z.string().nullable().optional(),
  volume: z.union([z.number(), z.string()]).nullable().optional(),
  liquidity: z.union([z.number(), z.string()]).nullable().optional(),
  endDate: z.string().nullable().optional(),
  outcomes: z.union([
    z.string(),
    z.array(z.string()),
    z.array(
      z.object({
        name: z.string(),
        price: z.union([z.number(), z.string()]).nullable().optional(),
      })
    ),
  ]).nullable().optional(),
  outcomePrices: z.string().nullable().optional(),
  isResolved: z.boolean().optional(),
  subMarketCount: z.number().optional(),
}).passthrough();

const incomingEventSchema = z.object({
  id: z.string(),
  title: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  slug: z.string().nullable().optional(),
  category: z.string().nullable().optional(),
  volume: z.union([z.number(), z.string()]).nullable().optional(),
  markets: z.array(incomingMarketSchema).default([]),
}).passthrough();

type IncomingMarket = z.infer<typeof incomingMarketSchema>;
type IncomingEvent = z.infer<typeof incomingEventSchema>;

interface ResearchRequest {
  main_event?: {
    title: string;
    description?: string;
  };
  sub_events: Array<{
    title: string;
    description?: string;
  }>;
}

interface ResearchResponse {
  main_event_research?: {
    summary?: string | null;
  } | null;
  synthesis?: string | null;
}

interface NormalizedMarket {
  id: string;
  title: string;
  slug: string;
  category: string;
  volume: number;
  liquidity: number;
  endDate: string;
  outcomes: Array<{ name: string; price: number }>;
  isResolved: boolean;
  subMarketCount?: number;
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function parseStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  if (typeof value !== "string" || !value.trim()) return [];
  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) {
      return parsed.map((item) => String(item).trim()).filter(Boolean);
    }
  } catch {
    // Fall through to CSV parsing
  }
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function parseNumberList(value: unknown): number[] {
  return parseStringList(value)
    .map((item) => Number.parseFloat(item))
    .filter((num) => Number.isFinite(num));
}

function normalizeOutcomes(market: IncomingMarket): Array<{ name: string; price: number }> {
  if (Array.isArray(market.outcomes) && market.outcomes.length > 0) {
    if (typeof market.outcomes[0] === "string") {
      const names = market.outcomes as string[];
      const prices = parseNumberList(market.outcomePrices);
      return names.map((name, idx) => ({ name, price: prices[idx] ?? 0.5 }));
    }

    const outcomeObjs = market.outcomes as Array<{ name: string; price?: number | string }>;
    const fallbackPrices = parseNumberList(market.outcomePrices);
    return outcomeObjs.map((outcome, idx) => ({
      name: outcome.name,
      price: toNumber(outcome.price) ?? fallbackPrices[idx] ?? 0.5,
    }));
  }

  const names = parseStringList(market.outcomes);
  if (names.length > 0) {
    const prices = parseNumberList(market.outcomePrices);
    return names.map((name, idx) => ({ name, price: prices[idx] ?? 0.5 }));
  }

  return [
    { name: "Yes", price: 0.5 },
    { name: "No", price: 0.5 },
  ];
}

function normalizeMarketForAnalysis(market: IncomingMarket, index: number, fallbackCategory: string): NormalizedMarket {
  return {
    id: market.id ?? `market-${index + 1}`,
    title: market.title ?? market.question ?? "Untitled market",
    slug: market.slug ?? market.id ?? `market-${index + 1}`,
    category: market.category ?? fallbackCategory,
    volume: toNumber(market.volume) ?? 0,
    liquidity: toNumber(market.liquidity) ?? 0,
    endDate: market.endDate ?? new Date().toISOString(),
    outcomes: normalizeOutcomes(market),
    isResolved: market.isResolved ?? false,
    subMarketCount: market.subMarketCount,
  };
}

function titleFromEvent(event: IncomingEvent): string {
  const directTitle = event.title?.trim();
  if (directTitle) return directTitle;
  const firstMarket = event.markets[0];
  const marketTitle = firstMarket?.title?.trim() || firstMarket?.question?.trim();
  if (marketTitle) return marketTitle;
  return event.id;
}

function buildResearchRequest(mainEvent: IncomingEvent, relatedEvents: IncomingEvent[]): ResearchRequest {
  const subEvents: ResearchRequest["sub_events"] = relatedEvents
    .map((event) => {
      const title = titleFromEvent(event);
      const description = event.description ?? undefined;
      return description ? { title, description } : { title };
    })
    .filter((event) => event.title.trim().length > 0);

  if (subEvents.length === 0) {
    const derived = mainEvent.markets
      .map((market) => ({
        title: market.question ?? market.title ?? "",
      }))
      .filter((market) => market.title.trim().length > 0)
      .slice(0, 5)
      .map((market) => ({ title: market.title }));

    subEvents.push(...derived);
  }

  if (subEvents.length === 0) {
    subEvents.push({ title: `${titleFromEvent(mainEvent)} market outlook` });
  }

  return {
    main_event: {
      title: titleFromEvent(mainEvent),
      description: mainEvent.description ?? undefined,
    },
    sub_events: subEvents,
  };
}

async function runResearch(input: ResearchRequest): Promise<ResearchResponse> {
  const RESEARCH_API_URL = process.env.RESEARCH_API_URL || "https://executable-easton-bifocal.ngrok-free.dev";
  const response = await fetch(`${RESEARCH_API_URL}/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    throw new Error(`Research API error: ${response.status}`);
  }

  return await response.json() as ResearchResponse;
}

// ─── New Tools: Event Explorer Flow ────────────────────────────────────────────

server.tool(
  {
    name: "get-events",
    description: "Search prediction market events by query. Calls the search API and returns ranked market results. Use when a user wants to explore events for a topic.",
    schema: z.object({
      query: z.string().optional().default("").describe("Search query to find events (e.g. 'presidential election', 'bitcoin', 'crypto', 'AI')"),
      n_results: z.number().optional().default(10).describe("Number of results to return"),
    }),
    widget: {
      name: "event-explorer",
      invoking: "Searching events...",
      invoked: "Events loaded",
    },
  },
  async ({ query, n_results }) => {
    const SEARCH_API_URL = process.env.SEARCH_API_URL || "https://executable-easton-bifocal.ngrok-free.dev";

    try {
      const response = await fetch(`${SEARCH_API_URL}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, n_results }),
      });

      if (!response.ok) {
        return widget({
          props: { results: [], expandedQueries: [], query },
          output: text(`Search API error: ${response.status} ${response.statusText}`),
        });
      }

      const data = await response.json() as {
        results: Array<Record<string, unknown>>;
        expanded_queries: string[];
      };

      return widget({
        props: {
          results: data.results,
          expandedQueries: data.expanded_queries,
          query,
        },
        output: text(
          `Found ${data.results.length} events matching "${query}"${data.expanded_queries.length > 0 ? ` (also searched: ${data.expanded_queries.join(", ")})` : ""}`
        ),
      });
    } catch (err) {
      return widget({
        props: { results: [], expandedQueries: [], query },
        output: text(`Failed to reach search API: ${err instanceof Error ? err.message : String(err)}`),
      });
    }
  }
);

server.listen().then(() => {
  console.log(`Server running`);
});
