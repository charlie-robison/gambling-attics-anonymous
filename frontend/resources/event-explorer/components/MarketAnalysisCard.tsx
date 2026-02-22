import React from "react";
import type { MarketSignal, MarketWithAction } from "../types";

const MIN_ORDER_SHARES = 5;

type OrderSide = "BUY" | "SELL";

type OrderFeedback = {
  kind: "success" | "error";
  message: string;
};

interface MarketAnalysisCardProps {
  market: MarketWithAction;
  signal?: MarketSignal;
  isSignalLoading?: boolean;
  onOpenMarket: (marketId: string, marketTitle: string) => void;
  onPlaceOrder: (
    marketId: string,
    side: OrderSide,
    amount: number
  ) => void;
  isBuyLoading?: boolean;
  isSellLoading?: boolean;
  orderFeedback?: OrderFeedback;
}

function formatVolume(value: number): string {
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(0)}M`;
  if (value >= 1_000) return `$${Math.round(value / 1_000)}K`;
  return `$${value.toFixed(0)}`;
}

function formatSignalLabel(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export const MarketAnalysisCard: React.FC<MarketAnalysisCardProps> = ({
  market,
  signal,
  isSignalLoading = false,
  onOpenMarket,
  onPlaceOrder,
  isBuyLoading = false,
  isSellLoading = false,
  orderFeedback,
}) => {
  const sortedOutcomes = [...market.outcomes].sort((a, b) => b.price - a.price).slice(0, 2);
  const yesOutcome = market.outcomes.find((o) => o.name.toLowerCase() === "yes");
  const currentPrice = yesOutcome ? yesOutcome.price : sortedOutcomes[0]?.price;
  const [orderAmount, setOrderAmount] = React.useState(String(MIN_ORDER_SHARES));

  const parsedAmount = Number.parseFloat(orderAmount);
  const isValidAmount = Number.isFinite(parsedAmount) && parsedAmount >= MIN_ORDER_SHARES;
  const isSubmitting = isBuyLoading || isSellLoading;

  return (
    <div
      className="market-card-v2 cursor-pointer"
      onClick={() => onOpenMarket(market.id, market.title)}
    >
      <h4 className="text-[14px] font-bold text-default leading-snug mb-2 line-clamp-2">
        {market.title}
      </h4>

      {currentPrice != null && (
        <div className="mb-3">
          <span className="text-2xl font-bold text-default tabular-nums">
            {Math.round(currentPrice * 100)}¢
          </span>
          <span className="text-xs text-secondary ml-1">
            {yesOutcome ? "Yes" : sortedOutcomes[0]?.name}
          </span>
        </div>
      )}

      {signal ? (
        <div className="mb-3 rounded-lg border border-[rgba(96,165,250,0.25)] bg-[rgba(96,165,250,0.08)] p-3">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <span className="category-badge" style={{ color: "#60a5fa" }}>
              Prediction: {signal.prediction.toUpperCase()}
            </span>
            <span className="category-badge">
              Confidence: {formatSignalLabel(signal.confidence)}
            </span>
          </div>
          <p className="text-xs text-secondary leading-relaxed whitespace-pre-wrap">
            {signal.rationale}
          </p>
        </div>
      ) : isSignalLoading ? (
        <div className="mb-3 rounded-lg border border-[rgba(96,165,250,0.25)] bg-[rgba(96,165,250,0.06)] p-3">
          <p className="text-xs text-secondary mb-2">Loading risk prediction...</p>
          <div className="space-y-2 animate-pulse">
            <div className="h-4 w-40 rounded bg-[rgba(255,255,255,0.12)]" />
            <div className="h-3 w-full rounded bg-[rgba(255,255,255,0.08)]" />
            <div className="h-3 w-[85%] rounded bg-[rgba(255,255,255,0.08)]" />
          </div>
        </div>
      ) : null}

      <div className="space-y-2 mb-3">
        {sortedOutcomes.map((outcome) => (
          <div key={outcome.name} className="flex items-center justify-between gap-2">
            <span className="text-xs text-secondary truncate flex-1">
              {outcome.name}
            </span>
            <span className="text-xs font-semibold text-default tabular-nums">
              {Math.round(outcome.price * 100)}%
            </span>
          </div>
        ))}
      </div>

      {market.position && (
        <div className="text-xs text-secondary mb-3 py-2 border-t border-[rgba(255,255,255,0.06)]">
          <span className="text-default font-medium">{market.position.shares}</span> shares @ {Math.round(market.position.avgPrice * 100)}%
          <span className={market.position.pnl >= 0 ? " text-[#60a5fa]" : " text-[#f87171]"}>
            {" "}({market.position.pnl >= 0 ? "+" : ""}{market.position.pnlPercent.toFixed(1)}%)
          </span>
        </div>
      )}

      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-secondary">{formatVolume(market.volume)}</span>
        <div className="flex items-center gap-2">
          <input
            type="number"
            inputMode="decimal"
            min={String(MIN_ORDER_SHARES)}
            step="0.01"
            value={orderAmount}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => setOrderAmount(e.target.value)}
            className="w-20 rounded-md border border-[rgba(255,255,255,0.15)] bg-[rgba(255,255,255,0.04)] px-2 py-1 text-xs text-default"
            aria-label={`Order amount for ${market.title}`}
          />
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (!isValidAmount || isSubmitting) return;
              onPlaceOrder(market.id, "BUY", parsedAmount);
            }}
            className="action-button--buy"
            disabled={!isValidAmount || isSubmitting}
          >
            {isBuyLoading ? "Buying..." : "Buy"}
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (!isValidAmount || isSubmitting) return;
              onPlaceOrder(market.id, "SELL", parsedAmount);
            }}
            className="action-button--sell"
            disabled={!isValidAmount || isSubmitting}
          >
            {isSellLoading ? "Selling..." : "Sell"}
          </button>
        </div>
      </div>
      {orderFeedback && (
        <p
          className="text-[11px] mt-2"
          style={{ color: orderFeedback.kind === "error" ? "#f87171" : "#60a5fa" }}
        >
          {orderFeedback.message}
        </p>
      )}
    </div>
  );
};
