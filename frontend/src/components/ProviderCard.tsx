import type { ProviderHealth } from "@/lib/types";
import LatencyChart from "./LatencyChart";

const STATUS = {
  operational: { label: "Operational", dot: "bg-emerald-400", text: "text-emerald-400", line: "#34d399" },
  degraded: { label: "Degraded", dot: "bg-amber-400", text: "text-amber-400", line: "#fbbf24" },
  down: { label: "Down", dot: "bg-rose-500", text: "text-rose-500", line: "#fb7185" },
  unknown: { label: "Unknown", dot: "bg-white/30", text: "text-white/40", line: "#9ca3af" },
} as const;

export default function ProviderCard({ p }: { p: ProviderHealth }) {
  const s = STATUS[p.status];
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold text-white">{p.name}</h3>
          {p.tier ? (
            <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-white/60">
              {p.tier}
            </span>
          ) : null}
        </div>
        <span className={`inline-flex items-center gap-2 text-sm font-medium ${s.text}`}>
          <span className={`h-2.5 w-2.5 rounded-full ${s.dot} animate-pulse`} />
          {s.label}
        </span>
      </div>
      {p.model ? (
        <p className="mt-1 truncate font-mono text-xs text-white/40">{p.model}</p>
      ) : null}

      <div className="mt-4 flex items-baseline gap-2">
        <span className="text-4xl font-bold text-white tabular-nums">{p.healthScore}</span>
        <span className="text-sm text-white/40">/ 100 health</span>
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
        <div>
          <dt className="text-xs text-white/40">Latency</dt>
          <dd className="text-sm font-medium text-white tabular-nums">{p.latencyMs}ms</dd>
        </div>
        <div>
          <dt className="text-xs text-white/40">Tokens/s</dt>
          <dd className="text-sm font-medium text-white tabular-nums">{p.tokenRate}</dd>
        </div>
        <div>
          <dt className="text-xs text-white/40">QA probe</dt>
          <dd className={`text-sm font-medium ${p.qaCorrect ? "text-emerald-400" : "text-rose-500"}`}>
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
