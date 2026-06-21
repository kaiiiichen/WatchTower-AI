import type { ProviderHealth } from "@/lib/types";
import { STATUS_STYLES, PROVIDER_OK, SEMANTIC_COLORS, monoSm, typeLg, typeMd, typeMdSemibold, typeSm } from "@/lib/style-maps";
import LatencyChart from "./LatencyChart";
import MagChip from "./mag-chip";

export default function ProviderCard({ p }: { p: ProviderHealth }) {
  const s = STATUS_STYLES[p.status];
  return (
    <div className="mag-card">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <h3 style={typeLg} className="text-zinc-900 dark:text-zinc-100 truncate">
            {p.name}
          </h3>
          {p.tier ? (
            <MagChip as="span" size="sm">
              {p.tier}
            </MagChip>
          ) : null}
        </div>
        <span style={typeMdSemibold} className={`inline-flex items-center gap-2 shrink-0 ${s.text}`}>
          <span className={`h-2.5 w-2.5 rounded-full ${s.dot} animate-pulse`} />
          {s.label}
        </span>
      </div>
      {p.model ? (
        <p className="mt-1 truncate text-zinc-400 dark:text-zinc-500" style={monoSm}>
          {p.model}
        </p>
      ) : null}

      {p.status === "degrading" ? (
        <p
          style={typeMd}
          className={`mt-2 rounded-md px-2 py-1 ${SEMANTIC_COLORS.amber.inset} ${SEMANTIC_COLORS.amber.textEmphasis}`}
        >
          Performance trending down — heads-up before any outage.
        </p>
      ) : null}

      <div className="mt-4 flex items-baseline gap-2">
        <span style={typeLg} className="text-zinc-900 dark:text-zinc-100 tabular-nums">
          {p.healthScore}
        </span>
        <span style={typeMd} className="text-zinc-400 dark:text-zinc-500">
          / 100 health
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
        <div>
          <dt style={typeSm} className="text-zinc-400 dark:text-zinc-500">
            Latency
          </dt>
          <dd style={typeMdSemibold} className="text-zinc-800 dark:text-zinc-200 tabular-nums">
            {p.latencyMs}ms
          </dd>
        </div>
        <div>
          <dt style={typeSm} className="text-zinc-400 dark:text-zinc-500">
            Tokens/s
          </dt>
          <dd style={typeMdSemibold} className="text-zinc-800 dark:text-zinc-200 tabular-nums">
            {p.tokenRate}
          </dd>
        </div>
        <div>
          <dt style={typeSm} className="text-zinc-400 dark:text-zinc-500">
            QA probe
          </dt>
          <dd style={typeMdSemibold} className={p.qaCorrect ? PROVIDER_OK.text : SEMANTIC_COLORS.rose.text}>
            {p.qaCorrect ? "Pass" : "Fail"}
          </dd>
        </div>
      </dl>

      <div className="mt-4">
        <LatencyChart data={p.latencyHistory} color={s.line} />
      </div>
    </div>
  );
}
