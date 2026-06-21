import type { OfficialStatusSignal } from "@/lib/types";
import { OFFICIAL_STYLES } from "@/lib/style-maps";

export default function OfficialStatus({
  signals,
}: {
  signals: OfficialStatusSignal[];
}) {
  if (!signals.length) return null;
  return (
    <section className="mt-8">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-white/50">
          Official status
        </h2>
        <span className="text-xs text-white/30">
          Provider status pages · corroboration + attribution
        </span>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {signals.map((sig) => (
          <OfficialCard key={sig.providerId} sig={sig} />
        ))}
      </div>
    </section>
  );
}

function OfficialCard({ sig }: { sig: OfficialStatusSignal }) {
  const s = OFFICIAL_STYLES[sig.status];
  const unavailable = sig.status === "unavailable";
  const active = sig.active && !unavailable;

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-white">{sig.providerId}</span>
        <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${s.text}`}>
          <span
            className={`h-2 w-2 rounded-full ${s.dot} ${
              active ? "animate-pulse" : ""
            }`}
          />
          {s.label}
        </span>
      </div>

      {unavailable ? (
        <p className="mt-3 text-xs text-white/40">
          Could not reach the status page — probes unaffected.
        </p>
      ) : active ? (
        <>
          {sig.headline ? (
            <p className="mt-3 text-sm font-medium text-white">{sig.headline}</p>
          ) : null}
          {sig.impactLabel ? (
            <p className="mt-1 text-xs text-amber-300/80">{sig.impactLabel}</p>
          ) : null}
          {sig.latestPhase && sig.latestUpdate ? (
            <p className="mt-2 text-xs leading-relaxed text-white/60">
              <span className="font-medium uppercase text-white/40">
                {sig.latestPhase}
              </span>
              {" · "}
              {sig.latestUpdate}
            </p>
          ) : null}
          {sig.componentSummary ? (
            <p className="mt-2 font-mono text-[10px] text-white/35">
              {sig.componentSummary}
            </p>
          ) : null}
        </>
      ) : (
        <p className="mt-3 text-xs text-emerald-300/80">
          All monitored components operational on the official page.
        </p>
      )}

      {sig.pageUrl ? (
        <a
          href={sig.pageUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-block text-[11px] text-sky-400/80 hover:text-sky-300"
        >
          View status page →
        </a>
      ) : null}
    </div>
  );
}
