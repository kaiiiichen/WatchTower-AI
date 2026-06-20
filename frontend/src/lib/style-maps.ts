import type { AlertSeverity, ProviderStatus } from "./types";

export const STATUS_STYLES = {
  operational: { label: "Operational", dot: "bg-emerald-400", text: "text-emerald-400", line: "#34d399" },
  degraded: { label: "Degraded", dot: "bg-amber-400", text: "text-amber-400", line: "#fbbf24" },
  down: { label: "Down", dot: "bg-rose-500", text: "text-rose-500", line: "#fb7185" },
  unknown: { label: "Unknown", dot: "bg-white/30", text: "text-white/40", line: "#9ca3af" },
} as const satisfies Record<ProviderStatus, { label: string; dot: string; text: string; line: string }>;

export const SEVERITY_STYLES = {
  info: "border-sky-500/40 bg-sky-500/10",
  warning: "border-amber-500/40 bg-amber-500/10",
  critical: "border-rose-500/40 bg-rose-500/10",
} as const satisfies Record<AlertSeverity, string>;
