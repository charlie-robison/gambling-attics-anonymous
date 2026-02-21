import { z } from "zod";

export const eventMarketSchema = z.object({
  id: z.string().optional().describe("Market ID"),
  title: z.string().optional().describe("Market title"),
  question: z.string().optional().describe("Market question"),
  category: z.string().nullable().optional().describe("Market category"),
  outcomes: z.string().nullable().optional().describe("Market outcomes (CSV or JSON string)"),
  outcomePrices: z.string().nullable().optional().describe("Market outcome prices (CSV or JSON string)"),
  volume: z.union([z.string(), z.number()]).nullable().optional().describe("Market volume"),
  liquidity: z.union([z.string(), z.number()]).nullable().optional().describe("Market liquidity"),
  endDate: z.string().nullable().optional().describe("Market end date"),
  active: z.boolean().nullable().optional().describe("Whether market is active"),
  closed: z.boolean().nullable().optional().describe("Whether market is closed"),
  slug: z.string().nullable().optional().describe("Market slug"),
  conditionId: z.string().nullable().optional().describe("Condition ID"),
});

export const marketResultSchema = z.object({
  id: z.string().describe("Market ID"),
  title: z.string().nullable().optional().describe("Event title"),
  description: z.string().nullable().optional().describe("Event description"),
  question: z.string().nullable().optional().describe("Market question"),
  category: z.string().nullable().optional().describe("Market category"),
  outcomes: z.string().nullable().optional().describe("Comma-separated outcomes"),
  outcomePrices: z.string().nullable().optional().describe("Comma-separated outcome prices"),
  volume: z.union([z.string(), z.number()]).nullable().optional().describe("Trading volume"),
  volumeNum: z.number().nullable().optional().describe("Trading volume as number"),
  liquidity: z.union([z.string(), z.number()]).nullable().optional().describe("Liquidity"),
  liquidityNum: z.number().nullable().optional().describe("Liquidity as number"),
  endDate: z.string().nullable().optional().describe("Market end date"),
  active: z.boolean().nullable().optional().describe("Whether market is active"),
  closed: z.boolean().nullable().optional().describe("Whether market is closed"),
  slug: z.string().nullable().optional().describe("Market slug"),
  conditionId: z.string().nullable().optional().describe("Condition ID"),
  markets: z.array(eventMarketSchema).optional().describe("Event markets"),
  relevance_score: z.number().describe("Relevance score from search"),
});

export const propsSchema = z.object({
  results: z.array(marketResultSchema).describe("Search results"),
  expandedQueries: z.array(z.string()).describe("Expanded search queries"),
  query: z.string().describe("The original search query"),
});

export const positionInfoSchema = z.object({
  id: z.string(),
  outcome: z.string(),
  shares: z.number(),
  avgPrice: z.number(),
  currentPrice: z.number(),
  pnl: z.number(),
  pnlPercent: z.number(),
});

export const outcomeSchema = z.object({
  name: z.string(),
  price: z.number(),
  imageUrl: z.string().optional(),
});

export const marketWithActionSchema = z.object({
  id: z.string(),
  title: z.string(),
  slug: z.string(),
  category: z.string(),
  volume: z.number(),
  liquidity: z.number(),
  endDate: z.string(),
  outcomes: z.array(outcomeSchema),
  imageUrl: z.string().optional(),
  isResolved: z.boolean(),
  resolvedOutcome: z.string().optional(),
  subMarketCount: z.number().optional(),
  userAction: z.enum(["buy", "sell", "hold"]),
  position: positionInfoSchema.nullable(),
});

export const eventInfoSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  slug: z.string(),
  category: z.string(),
  volume: z.number(),
});

export const analysisResultSchema = z.object({
  event: eventInfoSchema,
  markets: z.array(marketWithActionSchema),
  researchError: z.string().optional(),
});

export const sentimentRatingSchema = z.enum([
  "very_bearish",
  "bearish",
  "neutral",
  "bullish",
  "very_bullish",
]);

export const newsLinkSchema = z.object({
  title: z.string(),
  url: z.string(),
  snippet: z.string().optional().nullable(),
  published_date: z.string().optional().nullable(),
  source_name: z.string().optional().nullable(),
});

export const mainEventResearchSchema = z.object({
  event_title: z.string(),
  summary: z.string(),
  key_findings: z.array(z.string()),
  news_links: z.array(newsLinkSchema),
  sentiment: sentimentRatingSchema,
  sentiment_rationale: z.string(),
});

export const subEventResearchSchema = z.object({
  sub_event_id: z.string(),
  sub_event_title: z.string(),
  summary: z.string(),
  key_findings: z.array(z.string()),
  news_links: z.array(newsLinkSchema),
  sentiment: sentimentRatingSchema,
  sentiment_rationale: z.string(),
});

export const subEventRelationshipSchema = z.object({
  sub_event_id: z.string(),
  sub_event_title: z.string(),
  relationship_summary: z.string(),
  influencing_news: z.string(),
});

export const researchOutputSchema = z.object({
  main_event_research: mainEventResearchSchema.optional().nullable(),
  sub_event_research: z.array(subEventResearchSchema),
  relationships: z.array(subEventRelationshipSchema).optional().nullable(),
  synthesis: z.string(),
  research_timestamp: z.string(),
  disclaimer: z.string(),
});

export const researchInputSchema = z.object({
  main_event: z.object({
    title: z.string(),
    description: z.string().optional(),
  }).optional(),
  sub_events: z.array(
    z.object({
      id: z.string().optional(),
      title: z.string(),
      description: z.string().optional(),
    })
  ).min(1),
});

export const riskInputMarketSchema = z.object({
  id: z.string(),
  title: z.string(),
  current_price: z.number().min(0).max(1).optional(),
  description: z.string().optional(),
});

export const riskManagementInputSchema = z.object({
  research_output: z.record(z.string(), z.unknown()),
  main_event: z.object({
    title: z.string(),
    description: z.string().optional(),
  }),
  markets: z.array(riskInputMarketSchema).min(1),
});

export const predictionSchema = z.enum(["yes", "no"]);

export const confidenceLevelSchema = z.enum(["high", "medium", "low"]);

export const marketSignalSchema = z.object({
  market_id: z.string(),
  market_title: z.string(),
  prediction: predictionSchema,
  confidence: confidenceLevelSchema,
  rationale: z.string(),
});

export const riskAnalysisOutputSchema = z.object({
  event_title: z.string(),
  signals: z.array(marketSignalSchema),
  overall_analysis: z.string(),
  timestamp: z.string(),
  disclaimer: z.string(),
});

export type MarketResult = z.infer<typeof marketResultSchema>;
export type EventExplorerProps = z.infer<typeof propsSchema>;
export type EventInfo = z.infer<typeof eventInfoSchema>;
export type MarketWithAction = z.infer<typeof marketWithActionSchema>;
export type AnalysisResult = z.infer<typeof analysisResultSchema>;
export type SentimentRating = z.infer<typeof sentimentRatingSchema>;
export type NewsLink = z.infer<typeof newsLinkSchema>;
export type MainEventResearch = z.infer<typeof mainEventResearchSchema>;
export type SubEventResearch = z.infer<typeof subEventResearchSchema>;
export type SubEventRelationship = z.infer<typeof subEventRelationshipSchema>;
export type ResearchOutput = z.infer<typeof researchOutputSchema>;
export type ResearchInput = z.infer<typeof researchInputSchema>;
export type RiskManagementInput = z.infer<typeof riskManagementInputSchema>;
export type MarketSignal = z.infer<typeof marketSignalSchema>;
export type RiskAnalysisOutput = z.infer<typeof riskAnalysisOutputSchema>;
