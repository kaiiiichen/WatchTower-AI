import type {
  AlertSeverity,
  CommunitySignalStatus,
  DiagnosticStatus,
  ProviderStatus,
  VerdictKind,
} from "./types";

export const STATUS_STYLES = {
  operational: { label: "Operational", dot: "bg-emerald-400", text: "text-emerald-400", line: "#34d399" },
  degraded: { label: "Degraded", dot: "bg-amber-400", text: "text-amber-400", line: "#fbbf24" },
  // Red is reserved for genuine service outages so it stays meaningful.
  down: { label: "Down", dot: "bg-rose-500", text: "text-rose-500", line: "#fb7185" },
  // Account/config faults — "your problem", deliberately NOT red.
  rate_limited: { label: "Rate limited", dot: "bg-orange-400", text: "text-orange-400", line: "#fb923c" },
  misconfigured: { label: "Config", dot: "bg-yellow-400", text: "text-yellow-400", line: "#facc15" },
  unknown: { label: "Unknown", dot: "bg-white/30", text: "text-white/40", line: "#9ca3af" },
} as const satisfies Record<ProviderStatus, { label: string; dot: string; text: string; line: string }>;

export const SEVERITY_STYLES = {
  info: "border-sky-500/40 bg-sky-500/10",
  warning: "border-amber-500/40 bg-amber-500/10",
  critical: "border-rose-500/40 bg-rose-500/10",
} as const satisfies Record<AlertSeverity, string>;

export const DIAGNOSTIC_ICONS = {
  pass: { icon: "✅", text: "text-emerald-400" },
  fail: { icon: "❌", text: "text-rose-400" },
  unknown: { icon: "❔", text: "text-white/40" },
} as const satisfies Record<DiagnosticStatus, { icon: string; text: string }>;

// The verdict banner — the product's soul output. "Not your problem" reads green
// (relief), "your side" reads red (action needed), indeterminate stays neutral.
export const VERDICT_STYLES = {
  "service-side": { box: "border-emerald-500/40 bg-emerald-500/10", text: "text-emerald-300", tag: "Not your problem" },
  "all-clear": { box: "border-emerald-500/40 bg-emerald-500/10", text: "text-emerald-300", tag: "All clear" },
  // Your account layer (quota/config) — actionable, but not a broken environment.
  "account-side": { box: "border-amber-500/40 bg-amber-500/10", text: "text-amber-300", tag: "Your account" },
  "your-side": { box: "border-rose-500/50 bg-rose-500/15", text: "text-rose-300", tag: "Your problem" },
  indeterminate: { box: "border-white/15 bg-white/[0.04]", text: "text-white/60", tag: "Inconclusive" },
} as const satisfies Record<VerdictKind, { box: string; text: string; tag: string }>;

export const COMMUNITY_STYLES = {
  spike: { label: "Spike", dot: "bg-rose-500", text: "text-rose-400", bar: "bg-rose-500" },
  elevated: { label: "Elevated", dot: "bg-amber-400", text: "text-amber-300", bar: "bg-amber-400" },
  normal: { label: "Calm", dot: "bg-emerald-400", text: "text-emerald-300", bar: "bg-emerald-400" },
  unavailable: { label: "No signal", dot: "bg-white/30", text: "text-white/40", bar: "bg-white/20" },
} as const satisfies Record<
  CommunitySignalStatus,
  { label: string; dot: string; text: string; bar: string }
>;
