import type { Alert } from "@/lib/types";
import {
  SEMANTIC_COLORS,
  SEVERITY_COLORS,
  typeLg,
  typeMd,
  typeMdSemibold,
  typeSm,
  typeSmSemibold,
  type SemanticColorSet,
} from "@/lib/style-maps";

export default function AlertBanner({ alert }: { alert: Alert }) {
  const colors = SEVERITY_COLORS[alert.severity];

  return (
    <div className="mag-card">
      <div className={`mag-card-inset border-l-4 ${colors.accent} ${colors.inset}`}>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`mag-chip mag-chip-sm uppercase tracking-wide ${colors.chip}`}
            style={{ ...typeSmSemibold, letterSpacing: "0.08em" }}
          >
            <span className={`h-2 w-2 rounded-full ${colors.dot} animate-pulse`} />
            {alert.severity}
          </span>
          <h3 style={typeLg} className={colors.textEmphasis}>
            {alert.title}
          </h3>
          {alert.communityConfirmed ? (
            <span className={`mag-chip mag-chip-sm ${SEMANTIC_COLORS.rose.chip}`} style={typeSm}>
              <span className={`h-1.5 w-1.5 rounded-full ${SEMANTIC_COLORS.rose.dot}`} />
              Confirmed widespread · unacknowledged
            </span>
          ) : null}
          {alert.officialAcknowledged ? (
            <span className={`mag-chip mag-chip-sm ${SEMANTIC_COLORS.sky.chip}`} style={typeSm}>
              <span className={`h-1.5 w-1.5 rounded-full ${SEMANTIC_COLORS.sky.dot}`} />
              Official acknowledged
            </span>
          ) : null}
        </div>

        <p style={typeMd} className="mt-3 text-zinc-700 dark:text-zinc-300">
          {alert.insight}
        </p>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-start">
          <Field
            label="Whose problem?"
            value={alert.attribution}
            colors={colors}
            flexGrow={contentWeight(alert.attribution)}
          />
          <Field
            label="Est. recovery"
            value={alert.recoveryEta}
            colors={colors}
            flexGrow={contentWeight(alert.recoveryEta)}
          />
          <Field
            label="Recommended fallback"
            value={alert.recommendedAlternative}
            colors={colors}
            flexGrow={contentWeight(alert.recommendedAlternative)}
          />
        </div>
      </div>
    </div>
  );
}

function contentWeight(text: string): number {
  return Math.max(1, Math.pow(text.length, 0.75));
}

function Field({
  label,
  value,
  colors,
  flexGrow,
}: {
  label: string;
  value: string;
  colors: SemanticColorSet;
  flexGrow: number;
}) {
  return (
    <div
      style={{ flex: `${flexGrow} 1 0` }}
      className={`mag-card-inset !p-3 !shadow-[2px_2px_0_0_var(--color-border-tertiary)] ${colors.inset} min-w-0 flex flex-col`}
    >
      <div style={typeSm} className={colors.text}>
        {label}
      </div>
      <div style={typeMdSemibold} className={`mt-1 ${colors.textOnTint} leading-snug`}>
        {value}
      </div>
    </div>
  );
}
