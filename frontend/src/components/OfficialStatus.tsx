import type { OfficialStatusSignal } from "@/lib/types";
import { OFFICIAL_STYLES, SEMANTIC_COLORS, accentLink, monoSm, typeLg, typeMd, typeMdSemibold } from "@/lib/style-maps";

export default function OfficialStatus({
  signals,
}: {
  signals: OfficialStatusSignal[];
}) {
  if (!signals.length) return null;
  return (
    <section>
      <div className="mag-label">Official status</div>
      <p style={typeMd} className="-mt-2 mb-4 text-zinc-400 dark:text-zinc-600">
        If the provider already admits an outage here, that&apos;s your answer.
      </p>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
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
  const hasIncident = sig.active && !unavailable;
  const headline =
    sig.headline ??
    (!unavailable && sig.status === "operational"
      ? "All systems operational"
      : null);

  return (
    <div className="mag-card">
      <div className="flex items-center justify-between gap-2">
        <span style={typeLg} className="text-zinc-900 dark:text-zinc-100">
          {sig.providerId}
        </span>
        <span style={typeMdSemibold} className={`inline-flex items-center gap-1.5 shrink-0 ${s.text}`}>
          <span
            className={`h-2 w-2 rounded-full ${s.dot} ${hasIncident ? "animate-pulse" : ""}`}
          />
          {s.label}
        </span>
      </div>

      {unavailable ? (
        <p style={typeMd} className="mt-3 text-zinc-500 dark:text-zinc-400">
          Could not reach the status page — probes unaffected.
        </p>
      ) : (
        <>
          {headline ? (
            <p
              style={typeMdSemibold}
              className="mt-3 text-zinc-800 dark:text-zinc-200"
            >
              {headline}
            </p>
          ) : null}
          {hasIncident && sig.impactLabel ? (
            <p style={typeMd} className={`mt-1 ${SEMANTIC_COLORS.amber.text}`}>
              {sig.impactLabel}
            </p>
          ) : null}
          {hasIncident && sig.latestPhase && sig.latestUpdate ? (
            <p style={typeMd} className="mt-2 text-zinc-600 dark:text-zinc-400">
              <span className="uppercase text-zinc-400 dark:text-zinc-500">{sig.latestPhase}</span>
              {" · "}
              {sig.latestUpdate}
            </p>
          ) : null}
          {sig.componentSummary ? (
            <p className="mt-2 text-zinc-400 dark:text-zinc-500" style={monoSm}>
              {sig.componentSummary}
            </p>
          ) : null}
        </>
      )}

      {sig.pageUrl ? (
        <a
          href={sig.pageUrl}
          target="_blank"
          rel="noopener noreferrer"
          style={typeMd}
          className={`mt-3 inline-block ${accentLink}`}
        >
          View status page
        </a>
      ) : null}
    </div>
  );
}
