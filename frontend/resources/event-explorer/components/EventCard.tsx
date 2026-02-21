import React from "react";
import type { MarketResult } from "../types";

interface EventCardProps {
  market: MarketResult;
  onAnalyze: (marketId: string, question: string) => void;
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
  const names = outcomes.split(",").map((s) => s.trim());
  const priceVals = prices.split(",").map((s) => parseFloat(s.trim()));
  return names.map((name, i) => ({ name, price: priceVals[i] ?? 0 }));
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
  const parsed = parseOutcomes(market.outcomes, market.outcomePrices);
  const endDateStr = formatDate(market.endDate);

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
        {market.question || "Untitled Market"}
      </h3>

      {/* Outcomes with prices */}
      {parsed.length > 0 && (
        <div className={`flex flex-wrap gap-2 ${isMain ? "mb-4" : "mb-3"}`}>
          {parsed.slice(0, isMain ? 6 : 3).map((o) => (
            <span
              key={o.name}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
              style={{
                background: o.price >= 0.5 ? "rgba(74, 222, 128, 0.1)" : "rgba(255, 255, 255, 0.06)",
                color: o.price >= 0.5 ? "#4ade80" : "rgba(255, 255, 255, 0.7)",
                border: `1px solid ${o.price >= 0.5 ? "rgba(74, 222, 128, 0.2)" : "rgba(255, 255, 255, 0.1)"}`,
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
        {market.volumeNum != null && market.volumeNum > 0 && (
          <span>{formatVolume(market.volumeNum)} vol</span>
        )}
        {market.liquidityNum != null && market.liquidityNum > 0 && (
          <span>{formatVolume(market.liquidityNum)} liq</span>
        )}
        {endDateStr && <span>Ends {endDateStr}</span>}
        {isMain && (
          <span className="ml-auto text-xs font-medium" style={{ color: "rgba(74, 222, 128, 0.7)" }}>
            {Math.round(market.relevance_score * 100)}% match
          </span>
        )}
      </div>

      {/* Analyze button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onAnalyze(market.id, market.question || "");
        }}
        className="analyze-button"
      >
        Analyze
      </button>
    </div>
  );
};
