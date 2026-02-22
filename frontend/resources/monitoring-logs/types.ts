import { z } from "zod";

export const logEntrySchema = z.object({
  timestamp: z.string().describe("ISO 8601 timestamp"),
  event_id: z.string().describe("Event ID this log relates to"),
  event_title: z.string().describe("Event title"),
  action: z.string().describe("Description of what happened"),
  details: z.string().describe("Additional details"),
  level: z.enum(["info", "trade", "signal", "error"]).describe("Log level"),
});

export const propsSchema = z.object({
  logs: z.array(logEntrySchema).describe("Log entries from the monitoring agent"),
  activeMonitors: z.record(z.string(), z.string()).describe("Map of event_id to event_title for active monitors"),
});

export type LogEntry = z.infer<typeof logEntrySchema>;
export type MonitoringLogsProps = z.infer<typeof propsSchema>;
