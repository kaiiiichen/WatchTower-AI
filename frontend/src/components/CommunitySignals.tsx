import type { CommunitySignal } from "@/lib/types";
import { COMMUNITY_STYLES } from "@/lib/style-maps";

// Community-signal heat per provider — the Reddit "fast leg". Corroboration
// only: a spike alongside a probe anomaly confirms a widespread event, but this
// block is purely informational and degrades to "No signal" when Reddit is down.
export default function CommunitySignals({
  signals,
}: {
  signals: CommunitySignal[];
}) {
  if (!signals.length) return null;
  return (
    <section className="mt-8">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-white/50">
          Community signal
        </h2>
        <span className="text-xs text-white/30">
          Reddit outage chatter · corroboration only
        </span>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {signals.map((sig) => (
          <SignalCard key={sig.providerId} sig={sig} />
        ))}
      </div>
    </section>
  );
}

function SignalCard({ sig }: { sig: CommunitySignal }) {
  const s = COMMUNITY_STYLES[sig.status];
  const unavailable = sig.status === "unavailable";
  const pct = Math.min(100, Math.round(sig.complaintRate * 100));
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-white">{sig.providerId}</span>
          {sig.subreddit ? (
            <span className="font-mono text-xs text-white/40">
              r/{sig.subreddit}
            </span>
          ) : null}
        </div>
        <span
          className={`inline-flex items-center gap-1.5 text-xs font-medium ${s.text}`}
        >
          <span
            className={`h-2 w-2 rounded-full ${s.dot} ${
              sig.status === "spike" ? "animate-pulse" : ""
            }`}
          />
          {s.label}
        </span>
      </div>

      {unavailable ? (
        <p className="mt-3 text-xs text-white/40">
          Signal unavailable — main probes unaffected.
        </p>
      ) : (
        <>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-bold tabular-nums text-white">
              {pct}%
            </span>
            <span className="text-xs text-white/40">complaint rate</span>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
            <div
              className={`h-full ${s.bar}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-white/40 tabular-nums">
            {sig.matchedPosts}/{sig.postCount} posts · baseline{" "}
            {Math.round(sig.baseline * 100)}%
          </p>
        </>
      )}
    </div>
  );
}
