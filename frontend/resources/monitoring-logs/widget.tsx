import { McpUseProvider, useWidget, type WidgetMetadata } from "mcp-use/react";
import React, { useState } from "react";
import "../styles.css";
import type { LogEntry, MonitoringLogsProps } from "./types";
import { propsSchema } from "./types";

export const widgetMetadata: WidgetMetadata = {
  description: "Display activity logs from autonomous position monitoring agents",
  props: propsSchema,
  exposeAsTool: false,
  metadata: {
    prefersBorder: false,
    invoking: "Loading monitoring logs...",
    invoked: "Monitoring logs loaded",
  },
};

type LevelFilter = "all" | "info" | "trade" | "signal" | "error";

const LEVEL_STYLES: Record<LogEntry["level"], { bg: string; text: string; border: string; label: string }> = {
  info:   { bg: "rgba(148,163,184,0.08)", text: "#94a3b8", border: "#475569", label: "INFO" },
  trade:  { bg: "rgba(96,165,250,0.08)", text: "#60a5fa", border: "#3b82f6", label: "TRADE" },
  signal: { bg: "rgba(59,130,246,0.08)", text: "#3b82f6", border: "#2563eb", label: "SIGNAL" },
  error:  { bg: "rgba(239,68,68,0.08)", text: "#ef4444", border: "#dc2626", label: "ERROR" },
};

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return iso;
  }
}

const SkeletonLoader: React.FC = () => (
  <div style={{ padding: "24px" }}>
    {[1, 2, 3, 4, 5].map((i) => (
      <div
        key={i}
        style={{
          height: "52px",
          marginBottom: "8px",
          borderRadius: "8px",
          background: "linear-gradient(90deg, rgba(255,255,255,0.03) 25%, rgba(255,255,255,0.06) 50%, rgba(255,255,255,0.03) 75%)",
          backgroundSize: "200% 100%",
          animation: "shimmer 1.5s infinite",
        }}
      />
    ))}
    <style>{`@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
  </div>
);

const MonitoringLogs: React.FC = () => {
  const { props, isPending } = useWidget<MonitoringLogsProps>();
  const [filter, setFilter] = useState<LevelFilter>("all");

  if (isPending) {
    return (
      <McpUseProvider>
        <div
          style={{
            background: "#0c0e14",
            border: "1px solid #1e2030",
            borderRadius: "24px",
            fontFamily: "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace",
            overflow: "hidden",
          }}
        >
          <div style={{ padding: "24px 24px 16px" }}>
            <div style={{ fontSize: "11px", letterSpacing: "0.1em", textTransform: "uppercase", color: "#4a5568", marginBottom: "4px" }}>
              autonomous agent
            </div>
            <div style={{ fontSize: "20px", fontWeight: 700, color: "#e2e8f0", fontFamily: "'Space Grotesk', 'DM Sans', sans-serif" }}>
              Position Monitor — Activity Log
            </div>
          </div>
          <SkeletonLoader />
        </div>
      </McpUseProvider>
    );
  }

  const { logs, activeMonitors } = props;
  const monitorCount = Object.keys(activeMonitors).length;

  const filtered = filter === "all" ? logs : logs.filter((l) => l.level === filter);
  const sorted = [...filtered].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

  const filterButtons: { key: LevelFilter; label: string }[] = [
    { key: "all", label: "All" },
    { key: "info", label: "Info" },
    { key: "trade", label: "Trade" },
    { key: "signal", label: "Signal" },
    { key: "error", label: "Error" },
  ];

  return (
    <McpUseProvider>
      <div
        style={{
          background: "#0c0e14",
          border: "1px solid #1e2030",
          borderRadius: "24px",
          fontFamily: "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div style={{ padding: "24px 24px 16px" }}>
          <div style={{ fontSize: "11px", letterSpacing: "0.1em", textTransform: "uppercase", color: "#4a5568", marginBottom: "4px" }}>
            autonomous agent
          </div>
          <div
            style={{
              fontSize: "20px",
              fontWeight: 700,
              color: "#e2e8f0",
              fontFamily: "'Space Grotesk', 'DM Sans', sans-serif",
              marginBottom: "12px",
            }}
          >
            Position Monitor — Activity Log
          </div>

          {/* Status bar */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              padding: "10px 14px",
              background: "#111320",
              borderRadius: "10px",
              border: "1px solid #1e2030",
              marginBottom: "14px",
            }}
          >
            <div
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: monitorCount > 0 ? "#60a5fa" : "#475569",
                boxShadow: monitorCount > 0 ? "0 0 8px rgba(96,165,250,0.5)" : "none",
              }}
            />
            <span style={{ fontSize: "12px", color: monitorCount > 0 ? "#60a5fa" : "#64748b" }}>
              {monitorCount > 0
                ? `${monitorCount} active monitor${monitorCount !== 1 ? "s" : ""}`
                : "No active monitors"}
            </span>
            {monitorCount > 0 && (
              <span style={{ fontSize: "11px", color: "#475569", marginLeft: "auto" }}>
                {Object.values(activeMonitors).slice(0, 3).join(" / ")}
                {monitorCount > 3 && ` +${monitorCount - 3} more`}
              </span>
            )}
          </div>

          {/* Filter buttons */}
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
            {filterButtons.map(({ key, label }) => {
              const isActive = filter === key;
              const levelStyle = key !== "all" ? LEVEL_STYLES[key as LogEntry["level"]] : null;
              return (
                <button
                  key={key}
                  onClick={() => setFilter(key)}
                  style={{
                    padding: "5px 12px",
                    fontSize: "11px",
                    fontWeight: 600,
                    fontFamily: "inherit",
                    borderRadius: "6px",
                    border: "1px solid",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                    borderColor: isActive
                      ? levelStyle?.border ?? "#3b82f6"
                      : "#1e2030",
                    background: isActive
                      ? levelStyle?.bg ?? "rgba(59,130,246,0.08)"
                      : "transparent",
                    color: isActive
                      ? levelStyle?.text ?? "#3b82f6"
                      : "#64748b",
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Log entries */}
        <div style={{ padding: "0 24px 24px", maxHeight: "480px", overflowY: "auto" }}>
          {sorted.length === 0 ? (
            <div
              style={{
                padding: "48px 24px",
                textAlign: "center",
                color: "#374151",
                fontSize: "13px",
              }}
            >
              <div style={{ fontSize: "28px", marginBottom: "12px", opacity: 0.4 }}>~</div>
              No monitoring activity yet
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              {sorted.map((entry, idx) => {
                const style = LEVEL_STYLES[entry.level];
                return (
                  <div
                    key={`${entry.timestamp}-${idx}`}
                    style={{
                      display: "flex",
                      gap: "12px",
                      padding: "10px 12px",
                      borderRadius: "8px",
                      borderLeft: `3px solid ${style.border}`,
                      background: style.bg,
                      alignItems: "flex-start",
                      transition: "background 0.15s ease",
                    }}
                  >
                    {/* Timestamp */}
                    <span
                      style={{
                        fontSize: "10px",
                        color: "#475569",
                        whiteSpace: "nowrap",
                        paddingTop: "2px",
                        minWidth: "110px",
                      }}
                    >
                      {formatTimestamp(entry.timestamp)}
                    </span>

                    {/* Level badge */}
                    <span
                      style={{
                        fontSize: "9px",
                        fontWeight: 700,
                        letterSpacing: "0.05em",
                        color: style.text,
                        background: style.bg,
                        border: `1px solid ${style.border}`,
                        borderRadius: "4px",
                        padding: "2px 6px",
                        whiteSpace: "nowrap",
                        minWidth: "48px",
                        textAlign: "center",
                      }}
                    >
                      {style.label}
                    </span>

                    {/* Content */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "baseline", gap: "8px", marginBottom: "2px" }}>
                        <span style={{ fontSize: "12px", fontWeight: 600, color: "#e2e8f0" }}>
                          {entry.action}
                        </span>
                        <span
                          style={{
                            fontSize: "10px",
                            color: "#374151",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {entry.event_title}
                        </span>
                      </div>
                      {entry.details && (
                        <div
                          style={{
                            fontSize: "11px",
                            color: "#64748b",
                            lineHeight: 1.5,
                            wordBreak: "break-word",
                          }}
                        >
                          {entry.details}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </McpUseProvider>
  );
};

export default MonitoringLogs;
