import React from "react";
import type { MarketResult } from "../types";

interface EventCardProps {
  market: MarketResult;
  onAnalyze: (event: MarketResult) => void;
  isMain?: boolean;
}

function formatVolume(value: number): string {
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(0)}M`;
  if (value >= 1_000) return `$${Math.round(value / 1_000)}K`;
  return `$${value.toFixed(0)}`;
}

function parseOutcomes(outcomes?: string | null, prices?: string | null): { name: string; price: number }[] {
  if (!outcomes || !prices) return [];
  const names = parseStringList(outcomes);
  const priceVals = parseNumberList(prices);
  return names.map((name, i) => ({ name, price: priceVals[i] ?? 0 }));
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
  return value.split(",").map((s) => s.trim()).filter(Boolean);
}

function parseNumberList(value?: string | null): number[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) {
      return parsed.map((item) => Number(item)).filter((num) => Number.isFinite(num));
    }
  } catch {
    // Fall through to CSV parsing
  }
  return value
    .split(",")
    .map((s) => Number.parseFloat(s.trim()))
    .filter((num) => Number.isFinite(num));
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function formatDate(dateStr?: string | null): string | null {
  if (!dateStr) return null;
  try {
    return new Date(dateStr).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return null;
  }
}

export const EventCard: React.FC<EventCardProps> = ({ market, onAnalyze, isMain = false }) => {
  const primaryMarket = market.markets?.[0];
  const parsed = parseOutcomes(
    market.outcomes ?? primaryMarket?.outcomes,
    market.outcomePrices ?? primaryMarket?.outcomePrices
  );
  const endDateStr = formatDate(market.endDate ?? primaryMarket?.endDate);
  const title = market.title || market.question || "Untitled Event";
  const volume = market.volumeNum ?? toNumber(market.volume);
  const liquidity = market.liquidityNum ?? toNumber(market.liquidity);

  return (
    <div className={isMain ? "event-card event-card--main" : "event-card"}>
      {/* Category + status badges */}
      <div className="flex items-center gap-2 mb-3">
        {market.category && (
          <span className="category-badge">{market.category}</span>
        )}
        {market.closed && (
          <span className="category-badge" style={{ color: "#f87171" }}>Closed</span>
        )}
        {market.active === false && !market.closed && (
          <span className="category-badge" style={{ color: "#fbbf24" }}>Inactive</span>
        )}
      </div>

      {/* Question */}
      <h3 className={`font-bold text-default leading-snug ${isMain ? "text-lg mb-2" : "text-[15px] mb-2"}`}>
        {title}
      </h3>

      {/* Outcomes with prices */}
      {parsed.length > 0 && (
        <div className={`flex flex-wrap gap-2 ${isMain ? "mb-4" : "mb-3"}`}>
          {parsed.slice(0, isMain ? 6 : 3).map((o) => (
            <span
              key={o.name}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
              style={{
                background: o.name.toLowerCase() === "yes" ? "rgba(74, 222, 128, 0.1)" : o.name.toLowerCase() === "no" ? "rgba(248, 113, 113, 0.1)" : "rgba(255, 255, 255, 0.06)",
                color: o.name.toLowerCase() === "yes" ? "#4ade80" : o.name.toLowerCase() === "no" ? "#f87171" : "rgba(255, 255, 255, 0.7)",
                border: `1px solid ${o.name.toLowerCase() === "yes" ? "rgba(74, 222, 128, 0.2)" : o.name.toLowerCase() === "no" ? "rgba(248, 113, 113, 0.2)" : "rgba(255, 255, 255, 0.1)"}`,
              }}
            >
              <span>{o.name}</span>
              <span className="font-semibold">{Math.round(o.price * 100)}%</span>
            </span>
          ))}
          {parsed.length > (isMain ? 6 : 3) && (
            <span className="text-xs text-secondary self-center">+{parsed.length - (isMain ? 6 : 3)} more</span>
          )}
        </div>
      )}

      {/* Stats row */}
      <div className="flex items-center gap-4 mb-4 text-xs text-secondary">
        {volume != null && volume > 0 && (
          <span>{formatVolume(volume)} vol</span>
        )}
        {liquidity != null && liquidity > 0 && (
          <span>{formatVolume(liquidity)} liq</span>
        )}
        {endDateStr && <span>Ends {endDateStr}</span>}
        {isMain && (
          <span className="ml-auto text-xs font-medium" style={{ color: "rgba(96, 165, 250, 0.7)" }}>
            {Math.round(market.relevance_score * 100)}% match
          </span>
        )}
      </div>

      {/* Analyze button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onAnalyze(market);
        }}
        className="analyze-button"
      >
        Analyze
      </button>
    </div>
  );
};
