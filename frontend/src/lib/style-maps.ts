import type {
  AlertSeverity,
  CommunitySignalStatus,
  DiagnosticStatus,
  ProviderStatus,
  VerdictKind,
} from "./types";
import { SEMANTIC_COLORS, type SemanticColorSet } from "./semantic-colors";

/**
 * Domain style maps — import from here in components.
 * Semantic Tailwind hues live only in semantic-colors.ts (enforced by lint:colors).
 */

export { SEMANTIC_COLORS, semantic } from "./semantic-colors";
export type { SemanticHue, SemanticColorSet } from "./semantic-colors";

export const STATUS_STYLES = {
  operational: {
    label: "Operational",
    dot: SEMANTIC_COLORS.emerald.dot,
    text: SEMANTIC_COLORS.emerald.text,
    line: "#22c55e",
  },
  degrading: {
    label: "Trending down",
    dot: SEMANTIC_COLORS.amber.dot,
    text: SEMANTIC_COLORS.amber.textEmphasis,
    line: "#f59e0b",
  },
  degraded: {
    label: "Degraded",
    dot: SEMANTIC_COLORS.amber.dot,
    text: SEMANTIC_COLORS.amber.text,
    line: "#f59e0b",
  },
  down: {
    label: "Down",
    dot: SEMANTIC_COLORS.rose.dot,
    text: SEMANTIC_COLORS.rose.text,
    line: "#f43f5e",
  },
  rate_limited: {
    label: "Rate limited",
    dot: SEMANTIC_COLORS.amber.dot,
    text: SEMANTIC_COLORS.amber.text,
    line: "#f59e0b",
  },
  misconfigured: {
    label: "Config",
    dot: SEMANTIC_COLORS.amber.dot,
    text: SEMANTIC_COLORS.amber.text,
    line: "#f59e0b",
  },
  unknown: {
    label: "Unknown",
    dot: "bg-zinc-400",
    text: "text-zinc-500 dark:text-zinc-400",
    line: "#a1a1aa",
  },
} as const satisfies Record<
  ProviderStatus,
  { label: string; dot: string; text: string; line: string }
>;

/** Green on Provider cards — Operational status, QA pass */
export const PROVIDER_OK = {
  dot: STATUS_STYLES.operational.dot,
  text: STATUS_STYLES.operational.text,
  accent: SEMANTIC_COLORS.emerald.accent,
} as const;

export const SEVERITY_COLORS = {
  info: SEMANTIC_COLORS.sky,
  warning: SEMANTIC_COLORS.amber,
  critical: SEMANTIC_COLORS.rose,
} as const satisfies Record<AlertSeverity, SemanticColorSet>;

/** @deprecated Prefer SEVERITY_COLORS[hue].inset */
export const SEVERITY_STYLES = {
  info: SEVERITY_COLORS.info.inset,
  warning: SEVERITY_COLORS.warning.inset,
  critical: SEVERITY_COLORS.critical.inset,
} as const satisfies Record<AlertSeverity, string>;

export const DIAGNOSTIC_ICONS = {
  pass: { icon: null, text: PROVIDER_OK.text, dot: PROVIDER_OK.dot },
  fail: { icon: "❌", text: SEMANTIC_COLORS.rose.text, dot: SEMANTIC_COLORS.rose.dot },
  unknown: { icon: "❔", text: "text-zinc-500 dark:text-zinc-400", dot: "bg-zinc-400" },
} as const satisfies Record<
  DiagnosticStatus,
  { icon: string | null; text: string; dot: string }
>;

export const VERDICT_STYLES = {
  "service-side": {
    box: `border-l-4 ${PROVIDER_OK.accent}`,
    text: PROVIDER_OK.text,
    dot: PROVIDER_OK.dot,
    tag: "Not your problem",
  },
  "all-clear": {
    box: `border-l-4 ${PROVIDER_OK.accent}`,
    text: PROVIDER_OK.text,
    dot: PROVIDER_OK.dot,
    tag: "All clear",
  },
  "account-side": {
    box: SEMANTIC_COLORS.amber.inset,
    text: SEMANTIC_COLORS.amber.textEmphasis,
    dot: SEMANTIC_COLORS.amber.dot,
    tag: "Your account",
  },
  "your-side": {
    box: SEMANTIC_COLORS.rose.inset,
    text: SEMANTIC_COLORS.rose.textEmphasis,
    dot: SEMANTIC_COLORS.rose.dot,
    tag: "Your problem",
  },
  indeterminate: {
    box: "border border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900/40",
    text: "text-zinc-600 dark:text-zinc-300",
    dot: "bg-zinc-400",
    tag: "Inconclusive",
  },
} as const satisfies Record<
  VerdictKind,
  { box: string; text: string; dot: string; tag: string }
>;

export const COMMUNITY_STYLES = {
  spike: {
    label: "Spike",
    dot: SEMANTIC_COLORS.rose.dot,
    text: SEMANTIC_COLORS.rose.text,
    bar: SEMANTIC_COLORS.rose.dot,
  },
  elevated: {
    label: "Elevated",
    dot: SEMANTIC_COLORS.amber.dot,
    text: SEMANTIC_COLORS.amber.textEmphasis,
    bar: SEMANTIC_COLORS.amber.dot,
  },
  normal: {
    label: "Calm",
    dot: SEMANTIC_COLORS.emerald.dot,
    text: SEMANTIC_COLORS.emerald.text,
    bar: SEMANTIC_COLORS.emerald.dot,
  },
  unavailable: {
    label: "No signal",
    dot: "bg-zinc-400",
    text: "text-zinc-500 dark:text-zinc-400",
    bar: "bg-zinc-300 dark:bg-zinc-600",
  },
} as const satisfies Record<
  CommunitySignalStatus,
  { label: string; dot: string; text: string; bar: string }
>;

export const OFFICIAL_STYLES = {
  operational: {
    label: "Operational",
    dot: SEMANTIC_COLORS.emerald.dot,
    text: SEMANTIC_COLORS.emerald.text,
  },
  degraded: {
    label: "Degraded",
    dot: SEMANTIC_COLORS.amber.dot,
    text: SEMANTIC_COLORS.amber.text,
  },
  partial_outage: {
    label: "Partial outage",
    dot: SEMANTIC_COLORS.amber.dot,
    text: SEMANTIC_COLORS.amber.textEmphasis,
  },
  major_outage: {
    label: "Major outage",
    dot: SEMANTIC_COLORS.rose.dot,
    text: SEMANTIC_COLORS.rose.text,
  },
  maintenance: {
    label: "Maintenance",
    dot: SEMANTIC_COLORS.sky.dot,
    text: SEMANTIC_COLORS.sky.text,
  },
  unavailable: {
    label: "Unavailable",
    dot: "bg-zinc-400",
    text: "text-zinc-500 dark:text-zinc-400",
  },
} as const satisfies Record<
  import("./types").OfficialSignalStatus,
  { label: string; dot: string; text: string }
>;

export const nunito = { fontFamily: "'Nunito'", fontWeight: 400 } as const;
export const nunitoLight = { fontFamily: "'Nunito'", fontWeight: 300 } as const;
export const nunitoSemibold = { fontFamily: "'Nunito'", fontWeight: 600 } as const;

export {
  TYPE_SCALE,
  typeSm,
  typeSmSemibold,
  typeMd,
  typeMdSemibold,
  typeLg,
  typeLgLight,
  typeStat,
  monoSm,
} from "./typography";

export const accentLink =
  "underline underline-offset-2 decoration-zinc-300 dark:decoration-zinc-600 hover:text-[#C4894F] hover:decoration-[#C4894F] dark:hover:text-[#D9A870] dark:hover:decoration-[#D9A870] transition-colors duration-150";
