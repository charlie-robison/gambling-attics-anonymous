import { McpUseProvider, useWidget, type WidgetMetadata } from "mcp-use/react";
import React from "react";
import "../styles.css";
import { EventCard } from "./components/EventCard";
import { EventExplorerSkeleton } from "./components/EventExplorerSkeleton";
import type { EventExplorerProps } from "./types";
import { propsSchema } from "./types";

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

const EventExplorer: React.FC = () => {
  const { props, isPending, callTool } = useWidget<Props>();

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

  const handleAnalyze = (marketId: string, _question: string) => {
    callTool("analyze-event", { eventId: marketId });
  };

  const mainResult = results[0] ?? null;
  const otherResults = results.slice(1);

  return (
    <McpUseProvider>
      <div className="markets-container">
        {/* Header */}
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
          {mainResult ? (
            <>
              {/* Top result */}
              <EventCard
                market={mainResult}
                onAnalyze={handleAnalyze}
                isMain
              />

              {/* Other results */}
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
      </div>
    </McpUseProvider>
  );
};

export default EventExplorer;
