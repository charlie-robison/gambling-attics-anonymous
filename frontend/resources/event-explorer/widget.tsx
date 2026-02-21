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
  SentimentRating,
} from "./types";
import { propsSchema, researchInputSchema, researchOutputSchema } from "./types";

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
  "http://localhost:8000";

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

async function runResearch(input: ResearchInput): Promise<ResearchOutput> {
  const requestBody = researchInputSchema.parse(input);
  const response = await fetch(`${RESEARCH_API_URL.replace(/\/$/, "")}/research`, {
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
  const [isAnalyzing, setIsAnalyzing] = React.useState(false);
  const [researchError, setResearchError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setAnalysis(null);
    setResearch(null);
    setIsAnalyzing(false);
    setResearchError(null);
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
    setResearch(null);

    const fallbackAnalysis = buildFallbackAnalysis(selectedEvent);
    const researchInput = buildResearchInput(selectedEvent, results);
    setAnalysis(fallbackAnalysis);

    try {
      const response = await runResearch(researchInput);
      setResearch(response);
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

  const mainResult = results[0] ?? null;
  const otherResults = results.slice(1);
  const isAnalysisView = analysis !== null;
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
                    setResearchError(null);
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
                {isAnalyzing && !research && !researchError && (
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
                ) : (
                  <p className="text-sm text-secondary">
                    No research output returned.
                  </p>
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
                    onOpenMarket={handleMarketClick}
                  />
                ))}
              </div>
            </div>
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
