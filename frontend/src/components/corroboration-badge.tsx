import type { CorroborationSummary } from "@/lib/provider-aggregate";
import { SEMANTIC_COLORS, typeSmSemibold } from "@/lib/style-maps";

const HUE_CHIP: Record<CorroborationSummary["hue"], string> = {
  emerald: SEMANTIC_COLORS.emerald.chip,
  amber: SEMANTIC_COLORS.amber.chip,
  rose: SEMANTIC_COLORS.rose.chip,
  sky: SEMANTIC_COLORS.sky.chip,
  zinc: "text-zinc-600 dark:text-zinc-400 !border-zinc-200 dark:!border-zinc-700 !bg-zinc-50 dark:!bg-zinc-900/50",
};

const HUE_DOT: Record<CorroborationSummary["hue"], string> = {
  emerald: SEMANTIC_COLORS.emerald.dot,
  amber: SEMANTIC_COLORS.amber.dot,
  rose: SEMANTIC_COLORS.rose.dot,
  sky: SEMANTIC_COLORS.sky.dot,
  zinc: "bg-zinc-400",
};

export default function CorroborationBadge({
  summary,
  compact,
}: {
  summary: CorroborationSummary;
  compact?: boolean;
}) {
  return (
    <span
      className={`mag-chip mag-chip-sm inline-flex items-center gap-1.5 ${HUE_CHIP[summary.hue]}`}
      style={typeSmSemibold}
      title={summary.detail}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${HUE_DOT[summary.hue]}`} />
      {summary.label}
      {!compact ? (
        <span className="font-normal opacity-80 hidden sm:inline">· {summary.detail}</span>
      ) : null}
    </span>
  );
}
