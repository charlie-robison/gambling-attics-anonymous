import { McpUseProvider, useWidget, type WidgetMetadata } from "mcp-use/react";
import React from "react";
import "../styles.css";
import { EventCard } from "./components/EventCard";
import { EventExplorerSkeleton } from "./components/EventExplorerSkeleton";
import { MarketAnalysisCard } from "./components/MarketAnalysisCard";
import type {
  AnalysisResult,
  EventExplorerProps,
  MarketResult,
  NewsLink,
  ResearchInput,
  ResearchOutput,
  RiskAnalysisOutput,
  RiskManagementInput,
  SentimentRating,
} from "./types";
import {
  propsSchema,
  researchInputSchema,
  researchOutputSchema,
  riskAnalysisOutputSchema,
  riskManagementInputSchema,
} from "./types";

export const widgetMetadata: WidgetMetadata = {
  description: "Search and display prediction market results from the search API",
  props: propsSchema,
  exposeAsTool: false,
  metadata: {
    prefersBorder: false,
    invoking: "Searching events...",
    invoked: "Events loaded",
  },
};

type Props = EventExplorerProps;

const RESEARCH_API_URL =
  (globalThis as { __RESEARCH_API_URL?: string }).__RESEARCH_API_URL ??
  "https://executable-easton-bifocal.ngrok-free.dev";
const API_BASE_URL = RESEARCH_API_URL.replace(/\/$/, "");

type OrderSide = "BUY" | "SELL";

type OrderRequest = {
  token_id: string;
  amount: number;
  side: OrderSide;
};

type OrderFeedback = {
  kind: "success" | "error";
  message: string;
};

const MIN_ORDER_SHARES = 5;

function toNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return 0;
}

function parseStringList(value?: string | null): string[] {
  if (!value) return [];
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

function parseNumberList(value?: string | null): number[] {
  return parseStringList(value)
    .map((item) => Number.parseFloat(item))
    .filter((num) => Number.isFinite(num));
}

function parseOutcomes(
  outcomes?: string | null,
  outcomePrices?: string | null
): Array<{ name: string; price: number }> {
  const names = parseStringList(outcomes);
  if (names.length === 0) {
    return [
      { name: "Yes", price: 0.5 },
      { name: "No", price: 0.5 },
    ];
  }
  const prices = parseNumberList(outcomePrices);
  return names.map((name, index) => ({
    name,
    price: prices[index] ?? 0.5,
  }));
}

function inferCurrentPrice(outcomes?: string | null, outcomePrices?: string | null): number | undefined {
  const names = parseStringList(outcomes).map((name) => name.toLowerCase());
  const prices = parseNumberList(outcomePrices);
  if (prices.length === 0) return undefined;

  const yesIndex = names.findIndex((name) => name === "yes");
  const candidate = yesIndex >= 0 && prices[yesIndex] != null ? prices[yesIndex] : prices[0];
  if (!Number.isFinite(candidate) || candidate < 0 || candidate > 1) return undefined;
  return candidate;
}

function eventTitleFromResult(result: MarketResult): string {
  return result.title?.trim() || result.question?.trim() || result.id;
}

function buildResearchInput(
  selectedEvent: MarketResult,
  allResults: MarketResult[]
): ResearchInput {
  const sub_events = allResults
    .filter((result) => result.id !== selectedEvent.id)
    .slice(0, 2)
    .map((result) => {
      const title = eventTitleFromResult(result);
      const description = result.description ?? undefined;
      return description ? { title, description } : { title };
    })
    .filter((subEvent) => subEvent.title.length > 0);

  if (sub_events.length === 0) {
    sub_events.push({ title: `${eventTitleFromResult(selectedEvent)} market outlook` });
  }

  const description = selectedEvent.description ?? undefined;
  const main_event = description
    ? { title: eventTitleFromResult(selectedEvent), description }
    : { title: eventTitleFromResult(selectedEvent) };

  return {
    main_event,
    sub_events,
  };
}

function buildFallbackAnalysis(selectedEvent: MarketResult): AnalysisResult {
  const fallbackMarkets = (selectedEvent.markets ?? []).map((market, index) => ({
    id: market.id ?? `${selectedEvent.id}-market-${index + 1}`,
    title: market.title ?? market.question ?? `Market ${index + 1}`,
    slug: market.slug ?? market.id ?? `${selectedEvent.id}-market-${index + 1}`,
    category: market.category ?? selectedEvent.category ?? "General",
    volume: toNumber(market.volume),
    liquidity: toNumber(market.liquidity),
    endDate: market.endDate ?? new Date().toISOString(),
    outcomes: parseOutcomes(market.outcomes, market.outcomePrices),
    imageUrl: undefined,
    isResolved: Boolean(market.closed),
    resolvedOutcome: undefined,
    subMarketCount: undefined,
    userAction: "hold" as const,
    position: null,
  }));

  return {
    event: {
      id: selectedEvent.id,
      title: eventTitleFromResult(selectedEvent),
      description: selectedEvent.description ?? "No event description available.",
      slug: selectedEvent.slug ?? selectedEvent.id,
      category: selectedEvent.category ?? "General",
      volume: toNumber(selectedEvent.volumeNum ?? selectedEvent.volume),
    },
    markets: fallbackMarkets,
  };
}

function buildRiskInput(
  selectedEvent: MarketResult,
  researchOutput: ResearchOutput
): RiskManagementInput {
  const mainTitle = eventTitleFromResult(selectedEvent);
  const mainDescription = selectedEvent.description?.trim();

  const mappedMarkets = (selectedEvent.markets ?? []).map((market, index) => {
    const title = market.title?.trim() || market.question?.trim() || `Market ${index + 1}`;
    const currentPrice = inferCurrentPrice(market.outcomes, market.outcomePrices);
    const description = market.question?.trim() || undefined;
    const marketId = market.id ?? `${selectedEvent.id}-market-${index + 1}`;

    return {
      id: marketId,
      title,
      ...(typeof currentPrice === "number" ? { current_price: currentPrice } : {}),
      ...(description ? { description } : {}),
    };
  });

  const markets =
    mappedMarkets.length > 0
      ? mappedMarkets
      : [{ id: `${selectedEvent.id}-market-1`, title: `${mainTitle} market outlook` }];

  return {
    research_output: researchOutput,
    main_event: mainDescription
      ? {
          title: mainTitle,
          description: mainDescription,
        }
      : { title: mainTitle },
    markets,
  };
}

async function runResearch(input: ResearchInput): Promise<ResearchOutput> {
  const requestBody = researchInputSchema.parse(input);
  const response = await fetch(`${API_BASE_URL}/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    throw new Error(`Research API error: ${response.status} ${response.statusText}`);
  }

  const raw = await response.json();
  const parsed = researchOutputSchema.safeParse(raw);
  if (!parsed.success) {
    throw new Error(`Research response schema mismatch: ${parsed.error.issues[0]?.message ?? "invalid payload"}`);
  }
  return parsed.data;
}

async function runRiskAnalysis(input: RiskManagementInput): Promise<RiskAnalysisOutput> {
  const requestBody = riskManagementInputSchema.parse(input);
  const response = await fetch(`${API_BASE_URL}/risk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    throw new Error(`Risk API error: ${response.status} ${response.statusText}`);
  }

  const raw = await response.json();
  const parsed = riskAnalysisOutputSchema.safeParse(raw);
  if (!parsed.success) {
    throw new Error(`Risk response schema mismatch: ${parsed.error.issues[0]?.message ?? "invalid payload"}`);
  }
  return parsed.data;
}

async function placeOrder(request: OrderRequest): Promise<unknown> {
  const response = await fetch(`${API_BASE_URL}/order`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string" && body.detail.trim().length > 0) {
        detail = body.detail;
      }
    } catch {
      // Keep fallback detail
    }
    throw new Error(`Order API error: ${detail}`);
  }

  try {
    return await response.json();
  } catch {
    return null;
  }
}

function formatSentiment(sentiment: SentimentRating): string {
  return sentiment
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatTimestamp(value?: string): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function mergeNewsLinks(research: ResearchOutput): NewsLink[] {
  const links: NewsLink[] = [
    ...(research.main_event_research?.news_links ?? []),
    ...research.sub_event_research.flatMap((item) => item.news_links ?? []),
  ];

  const seen = new Set<string>();
  const deduped: NewsLink[] = [];
  for (const link of links) {
    if (!link.url || seen.has(link.url)) continue;
    seen.add(link.url);
    deduped.push(link);
  }
  return deduped;
}

const RESEARCH_STEPS = [
  "Searching for recent news...",
  "Gathering market data...",
  "Analyzing sentiment...",
  "Synthesizing findings...",
];

const ResearchLoadingIndicator: React.FC = () => {
  const [stepIndex, setStepIndex] = React.useState(0);

  React.useEffect(() => {
    const interval = setInterval(() => {
      setStepIndex((prev) => Math.min(prev + 1, RESEARCH_STEPS.length - 1));
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="mb-3">
      <div className="space-y-2 mb-3">
        {RESEARCH_STEPS.map((step, i) => (
          <div key={step} className="flex items-center gap-2">
            {i < stepIndex ? (
              <span className="text-xs" style={{ color: "#4ade80" }}>&#10003;</span>
            ) : i === stepIndex ? (
              <span className="research-spinner" />
            ) : (
              <span style={{ width: 14, height: 14 }} />
            )}
            <span
              className="text-sm"
              style={{
                color: i <= stepIndex ? "rgba(255,255,255,0.8)" : "rgba(255,255,255,0.3)",
              }}
            >
              {step}
            </span>
          </div>
        ))}
      </div>
      <div className="space-y-2">
        <div className="research-skeleton" style={{ width: "90%" }} />
        <div className="research-skeleton" style={{ width: "70%" }} />
        <div className="research-skeleton" style={{ width: "80%" }} />
      </div>
    </div>
  );
};

const EventExplorer: React.FC = () => {
  const { props, isPending, sendFollowUpMessage } = useWidget<Props>();
  const [analysis, setAnalysis] = React.useState<AnalysisResult | null>(null);
  const [research, setResearch] = React.useState<ResearchOutput | null>(null);
  const [riskAnalysis, setRiskAnalysis] = React.useState<RiskAnalysisOutput | null>(null);
  const [isAnalyzing, setIsAnalyzing] = React.useState(false);
  const [isRiskLoading, setIsRiskLoading] = React.useState(false);
  const [researchError, setResearchError] = React.useState<string | null>(null);
  const [riskError, setRiskError] = React.useState<string | null>(null);
  const [activeOrderKey, setActiveOrderKey] = React.useState<string | null>(null);
  const [orderFeedbackByMarket, setOrderFeedbackByMarket] = React.useState<
    Record<string, OrderFeedback>
  >({});
  const riskSignalsByMarketId = new Map(
    (riskAnalysis?.signals ?? []).map((signal) => [signal.market_id, signal])
  );

  React.useEffect(() => {
    setAnalysis(null);
    setResearch(null);
    setRiskAnalysis(null);
    setIsAnalyzing(false);
    setIsRiskLoading(false);
    setResearchError(null);
    setRiskError(null);
    setActiveOrderKey(null);
    setOrderFeedbackByMarket({});
  }, [props.query, props.results]);

  if (isPending) {
    return (
      <McpUseProvider>
        <div className="markets-container">
          <div className="p-6 pb-4">
            <h2 className="text-xl font-bold text-default mb-1">Events</h2>
            <div className="h-4 w-48 rounded-md bg-default/10 animate-pulse" />
          </div>
          <div className="px-6 pb-6">
            <EventExplorerSkeleton />
          </div>
        </div>
      </McpUseProvider>
    );
  }

  const { results, expandedQueries, query } = props;

  const handleAnalyze = async (selectedEvent: MarketResult) => {
    setIsAnalyzing(true);
    setResearchError(null);
    setRiskError(null);
    setResearch(null);
    setRiskAnalysis(null);
    setIsRiskLoading(false);

    const fallbackAnalysis = buildFallbackAnalysis(selectedEvent);
    const researchInput = buildResearchInput(selectedEvent, results);
    setAnalysis(fallbackAnalysis);

    try {
      const response = await runResearch(researchInput);
      setResearch(response);

      setIsRiskLoading(true);
      try {
        const riskInput = buildRiskInput(selectedEvent, response);
        const riskResponse = await runRiskAnalysis(riskInput);
        setRiskAnalysis(riskResponse);
      } catch (error) {
        setRiskError(error instanceof Error ? error.message : String(error));
      } finally {
        setIsRiskLoading(false);
      }
    } catch (error) {
      setResearchError(error instanceof Error ? error.message : String(error));
    }

    setIsAnalyzing(false);
  };

  const handleMarketClick = (marketId: string, marketTitle: string) => {
    sendFollowUpMessage(
      `Show me the detail for market "${marketTitle}" (marketId: ${marketId})`
    );
  };

  const handlePlaceOrder = async (
    marketId: string,
    side: OrderSide,
    amount: number
  ) => {
    if (!Number.isFinite(amount) || amount < MIN_ORDER_SHARES) {
      setOrderFeedbackByMarket((previous) => ({
        ...previous,
        [marketId]: {
          kind: "error",
          message: `Minimum order is ${MIN_ORDER_SHARES} shares`,
        },
      }));
      return;
    }

    const orderKey = `${marketId}:${side}`;
    setActiveOrderKey(orderKey);

    try {
      await placeOrder({
        token_id: marketId,
        amount,
        side,
      });
      setOrderFeedbackByMarket((previous) => ({
        ...previous,
        [marketId]: {
          kind: "success",
          message: `${side} order placed (${amount.toFixed(2)} shares)`,
        },
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setOrderFeedbackByMarket((previous) => ({
        ...previous,
        [marketId]: {
          kind: "error",
          message: `Failed to place ${side} order: ${message}`,
        },
      }));
    } finally {
      setActiveOrderKey((current) => (current === orderKey ? null : current));
    }
  };

  const mainResult = results[0] ?? null;
  const otherResults = results.slice(1);
  const isAnalysisView = analysis !== null;
  const isResearchReady = research !== null;
  const isResearchLoading = isAnalyzing && !isResearchReady && !researchError;
  const isRiskPending = isResearchReady && isRiskLoading && !riskAnalysis;
  const combinedNewsLinks = research ? mergeNewsLinks(research) : [];
  const mainEventResearch = research?.main_event_research ?? null;

  return (
    <McpUseProvider>
      <div className="markets-container">
        {isAnalysisView && analysis ? (
          <>
            <div className="px-6 pt-6 pb-2">
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="category-badge">{analysis.event.category}</span>
                <button
                  className="analyze-button"
                  onClick={() => {
                    setAnalysis(null);
                    setResearch(null);
                    setRiskAnalysis(null);
                    setResearchError(null);
                    setRiskError(null);
                    setIsRiskLoading(false);
                  }}
                >
                  Back to results
                </button>
              </div>
              <h2 className="text-xl font-bold text-default mb-1">
                {analysis.event.title}
              </h2>
            </div>

            <div className="px-6 pb-4">
              <div className="p-4 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)]">
                <p className="text-sm text-secondary leading-relaxed">
                  {analysis.event.description}
                </p>
              </div>
            </div>

            <div className="px-6 pb-4">
              <div className="p-4 rounded-xl border border-[rgba(74,222,128,0.25)] bg-[rgba(74,222,128,0.06)]">
                <div className="flex items-center justify-between gap-3 mb-3">
                  <h3 className="text-sm font-semibold text-default">Research</h3>
                  {mainEventResearch?.sentiment && (
                    <span className="category-badge">
                      {formatSentiment(mainEventResearch.sentiment)}
                    </span>
                  )}
                </div>

                {researchError && (
                  <p className="text-sm mb-3" style={{ color: "#f87171" }}>
                    Failed to fetch research: {researchError}
                  </p>
                )}
                {isResearchLoading && (
                  <ResearchLoadingIndicator />
                )}

                {research ? (
                  <div className="space-y-4">
                    {research.synthesis && (
                      <div>
                        <h4 className="text-xs font-semibold text-default mb-2 uppercase tracking-[0.5px]">
                          Synthesis
                        </h4>
                        <p className="text-sm text-secondary leading-relaxed whitespace-pre-wrap">
                          {research.synthesis}
                        </p>
                      </div>
                    )}

                    {research.relationships && research.relationships.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold text-default mb-2 uppercase tracking-[0.5px]">
                          Related Sub-Events
                        </h4>
                        <div className="space-y-2">
                          {research.relationships.map((relationship) => (
                            <div
                              key={relationship.sub_event_id}
                              className="rounded-lg border border-[rgba(255,255,255,0.08)] p-3 bg-[rgba(255,255,255,0.02)]"
                            >
                              <p className="text-xs font-semibold text-default mb-1">
                                {relationship.sub_event_title}
                              </p>
                              <p className="text-xs text-secondary leading-relaxed mb-2">
                                {relationship.relationship_summary}
                              </p>
                              <p className="text-[11px] text-secondary leading-relaxed">
                                <span className="text-default font-medium">Influencing news:</span>{" "}
                                {relationship.influencing_news}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {mainEventResearch?.summary && (
                      <div>
                        <h4 className="text-xs font-semibold text-default mb-2 uppercase tracking-[0.5px]">
                          Main Event Summary
                        </h4>
                        <p className="text-xs text-secondary leading-relaxed whitespace-pre-wrap">
                          {mainEventResearch.summary}
                        </p>
                      </div>
                    )}

                    {mainEventResearch?.sentiment_rationale && (
                      <p className="text-xs text-secondary">
                        <span className="text-default font-medium">Sentiment rationale:</span>{" "}
                        {mainEventResearch.sentiment_rationale}
                      </p>
                    )}

                    {mainEventResearch && mainEventResearch.key_findings.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold text-default mb-2 uppercase tracking-[0.5px]">
                          Key Findings
                        </h4>
                        <ul className="list-disc pl-5 space-y-1">
                          {mainEventResearch.key_findings.slice(0, 7).map((finding) => (
                            <li key={finding} className="text-sm text-secondary">
                              {finding}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {combinedNewsLinks.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold text-default mb-2 uppercase tracking-[0.5px]">
                          News Sources
                        </h4>
                        <div className="space-y-2">
                          {combinedNewsLinks.slice(0, 6).map((link) => (
                            <a
                              key={link.url}
                              href={link.url}
                              target="_blank"
                              rel="noreferrer"
                              className="block rounded-lg border border-[rgba(255,255,255,0.08)] p-3 bg-[rgba(255,255,255,0.02)] hover:bg-[rgba(255,255,255,0.04)]"
                            >
                              <p className="text-xs font-semibold text-default line-clamp-2">{link.title}</p>
                              {(link.source_name || link.published_date) && (
                                <p className="text-[11px] text-secondary mt-1">
                                  {[link.source_name, link.published_date].filter(Boolean).join(" • ")}
                                </p>
                              )}
                              {link.snippet && (
                                <p className="text-xs text-secondary mt-1 line-clamp-2">{link.snippet}</p>
                              )}
                            </a>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="pt-1">
                      <p className="text-[11px] text-secondary">
                        Research generated {formatTimestamp(research.research_timestamp)}
                      </p>
                      {research.disclaimer && (
                        <p className="text-[11px] text-secondary mt-1">{research.disclaimer}</p>
                      )}
                    </div>
                  </div>
                ) : !isResearchLoading ? (
                  <p className="text-sm text-secondary">
                    No research output returned.
                  </p>
                ) : null}
              </div>
            </div>

            {isResearchReady && (
              <>
                <div className="px-6 pb-4">
                  <div className="p-4 rounded-xl border border-[rgba(96,165,250,0.25)] bg-[rgba(96,165,250,0.06)]">
                    <h3 className="text-sm font-semibold text-default mb-3">Analysis</h3>
                    {riskError && (
                      <p className="text-sm mb-3" style={{ color: "#f87171" }}>
                        Failed to fetch risk analysis: {riskError}
                      </p>
                    )}
                    {isRiskPending && (
                      <div className="mb-3">
                        <p className="text-sm mb-2 text-secondary">Running risk analysis...</p>
                        <div className="space-y-2 animate-pulse">
                          <div className="h-3 w-full rounded bg-[rgba(255,255,255,0.10)]" />
                          <div className="h-3 w-[92%] rounded bg-[rgba(255,255,255,0.08)]" />
                          <div className="h-3 w-[78%] rounded bg-[rgba(255,255,255,0.08)]" />
                        </div>
                      </div>
                    )}

                    {riskAnalysis ? (
                      <div className="space-y-3">
                        <p className="text-sm text-secondary leading-relaxed whitespace-pre-wrap">
                          {riskAnalysis.overall_analysis}
                        </p>
                        <div>
                          <p className="text-[11px] text-secondary">
                            Analysis generated {formatTimestamp(riskAnalysis.timestamp)}
                          </p>
                          {riskAnalysis.disclaimer && (
                            <p className="text-[11px] text-secondary mt-1">{riskAnalysis.disclaimer}</p>
                          )}
                        </div>
                      </div>
                    ) : (
                      !isRiskPending &&
                      !riskError && (
                        <p className="text-sm text-secondary">
                          No risk analysis output returned.
                        </p>
                      )
                    )}
                  </div>
                </div>

                <div className="px-6 pb-6">
                  <h3 className="text-sm font-semibold text-secondary mb-4">
                    {analysis.markets.length} Market{analysis.markets.length !== 1 ? "s" : ""}
                  </h3>
                  <div className="analysis-grid">
                    {analysis.markets.map((market) => (
                      <MarketAnalysisCard
                        key={market.id}
                        market={market}
                        signal={riskSignalsByMarketId.get(market.id)}
                        isSignalLoading={isRiskPending}
                        onOpenMarket={handleMarketClick}
                        onPlaceOrder={handlePlaceOrder}
                        isBuyLoading={activeOrderKey === `${market.id}:BUY`}
                        isSellLoading={activeOrderKey === `${market.id}:SELL`}
                        orderFeedback={orderFeedbackByMarket[market.id]}
                      />
                    ))}
                  </div>
                </div>
              </>
            )}
            {!isResearchReady && isResearchLoading ? (
              <div className="px-6 pb-6">
                <div className="rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.03)] p-4">
                  <p className="text-sm text-secondary">Preparing market analysis after research completes...</p>
                </div>
              </div>
            ) : null}
            {!isResearchReady && researchError ? (
              <div className="px-6 pb-6">
                <div className="rounded-xl border border-[rgba(248,113,113,0.35)] bg-[rgba(248,113,113,0.08)] p-4">
                  <p className="text-sm" style={{ color: "#fca5a5" }}>
                    Analysis is hidden because research did not complete.
                  </p>
                </div>
              </div>
            ) : null}
          </>
        ) : (
          <>
            <div className="px-6 pt-6 pb-4">
              <h2 className="text-xl font-bold text-default">
                Results for "{query}"
              </h2>
              {expandedQueries.length > 0 && (
                <p className="text-xs text-secondary mt-1">
                  Also searched: {expandedQueries.join(", ")}
                </p>
              )}
            </div>

            <div className="px-6 pb-6">
              {isAnalyzing && (
                <div className="mb-4 flex items-center gap-2">
                  <span className="research-spinner" />
                  <span className="text-sm text-secondary">Analyzing event...</span>
                </div>
              )}
              {mainResult ? (
                <>
                  <EventCard
                    market={mainResult}
                    onAnalyze={handleAnalyze}
                    isMain
                  />
                  {otherResults.length > 0 && (
                    <>
                      <h3 className="text-sm font-semibold text-secondary mt-6 mb-4">
                        More Results
                      </h3>
                      <div className="related-events-row">
                        {otherResults.map((market) => (
                          <EventCard
                            key={market.id}
                            market={market}
                            onAnalyze={handleAnalyze}
                          />
                        ))}
                      </div>
                    </>
                  )}
                </>
              ) : (
                <div className="py-8 text-center text-secondary text-sm">
                  No markets found matching "{query}"
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </McpUseProvider>
  );
};

export default EventExplorer;
