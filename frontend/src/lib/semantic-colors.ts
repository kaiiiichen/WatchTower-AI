/**
 * WatchTower semantic color palette — **single source of truth**.
 *
 * ┌─────────────────────────────────────────────────────────────┐
 * │  Agents: do NOT add text-rose-*, bg-emerald-*, etc. in      │
 * │  components. Import SEMANTIC_COLORS / style-maps instead.   │
 * │  See frontend/AGENTS.md · npm run lint:colors               │
 * └─────────────────────────────────────────────────────────────┘
 *
 * Hues: rose · emerald · amber · sky  (Detection Gap palette)
 * Card chrome (zinc borders, --accent bronze) is separate — not part of this set.
 * Each hue: inset, accent, text, textStrong, textEmphasis, textOnTint, dot, bar, barSoft, chip
 */
export type SemanticHue = "rose" | "emerald" | "amber" | "sky";

export type SemanticColorSet = {
  /** Tinted mag-card-inset panel */
  inset: string;
  /** Left accent stripe */
  accent: string;
  text: string;
  textStrong: string;
  textEmphasis: string;
  textOnTint: string;
  dot: string;
  bar: string;
  barSoft: string;
  chip: string;
};

export const SEMANTIC_COLORS = {
  rose: {
    inset: "border border-rose-200 dark:border-rose-800 bg-rose-50 dark:bg-rose-950/40",
    accent: "border-l-rose-500 dark:border-l-rose-400",
    text: "text-rose-600 dark:text-rose-400",
    textStrong: "text-rose-600 dark:text-rose-400",
    textEmphasis: "text-rose-700 dark:text-rose-300",
    textOnTint: "text-rose-800 dark:text-rose-200",
    dot: "bg-rose-500",
    bar: "bg-rose-500/70",
    barSoft: "bg-rose-400/80",
    chip:
      "text-rose-700 dark:text-rose-300 !border-rose-200 dark:!border-rose-800 !bg-rose-50 dark:!bg-rose-950/60",
  },
  emerald: {
    inset: "border border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/40",
    accent: "border-l-emerald-500 dark:border-l-emerald-400",
    text: "text-emerald-600 dark:text-emerald-400",
    textStrong: "text-emerald-600 dark:text-emerald-400",
    textEmphasis: "text-emerald-700 dark:text-emerald-300",
    textOnTint: "text-emerald-800 dark:text-emerald-200",
    dot: "bg-emerald-500",
    bar: "bg-emerald-500/70",
    barSoft: "bg-emerald-400/80",
    chip:
      "text-emerald-700 dark:text-emerald-300 !border-emerald-200 dark:!border-emerald-800 !bg-emerald-50 dark:!bg-emerald-950/60",
  },
  amber: {
    inset: "border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40",
    accent: "border-l-amber-500 dark:border-l-amber-400",
    text: "text-amber-600 dark:text-amber-400",
    textStrong: "text-amber-600 dark:text-amber-400",
    textEmphasis: "text-amber-700 dark:text-amber-300",
    textOnTint: "text-amber-800 dark:text-amber-200",
    dot: "bg-amber-500",
    bar: "bg-amber-500/70",
    barSoft: "bg-amber-400/80",
    chip:
      "text-amber-700 dark:text-amber-300 !border-amber-200 dark:!border-amber-800 !bg-amber-50 dark:!bg-amber-950/60",
  },
  sky: {
    inset: "border border-sky-200 dark:border-sky-800 bg-sky-50 dark:bg-sky-950/40",
    accent: "border-l-sky-500 dark:border-l-sky-400",
    text: "text-sky-600 dark:text-sky-400",
    textStrong: "text-sky-600 dark:text-sky-400",
    textEmphasis: "text-sky-700 dark:text-sky-300",
    textOnTint: "text-sky-800 dark:text-sky-200",
    dot: "bg-sky-500",
    bar: "bg-sky-500/70",
    barSoft: "bg-sky-400/80",
    chip:
      "text-sky-700 dark:text-sky-300 !border-sky-200 dark:!border-sky-800 !bg-sky-50 dark:!bg-sky-950/60",
  },
} as const satisfies Record<SemanticHue, SemanticColorSet>;

/** Shorthand accessor for a hue's class bundle */
export function semantic(hue: SemanticHue): SemanticColorSet {
  return SEMANTIC_COLORS[hue];
}
