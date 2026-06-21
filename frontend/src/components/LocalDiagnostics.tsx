"use client";

import { useState } from "react";
import type { EnvironmentProfile, LocalDiagnosis } from "@/lib/types";
import { DIAGNOSTIC_ICONS, VERDICT_STYLES } from "@/lib/style-maps";

// Local environment diagnostics — answers "is it your problem or the service's?".
// Runs on demand (a button), shows each check ✅/❌/❔ and a prominent verdict.
export default function LocalDiagnostics() {
  const [diag, setDiag] = useState<LocalDiagnosis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/diagnose", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setDiag((await res.json()) as LocalDiagnosis);
    } catch (e) {
      setError(e instanceof Error ? e.message : "diagnose failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="mt-8 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-white/50">
            Local diagnostics
          </h2>
          <p className="mt-1 text-xs text-white/40">
            Is it your environment or the service? Checks DNS · TCP:443 · API key.
          </p>
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="rounded-lg bg-white/10 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/20 disabled:opacity-50"
        >
          {loading ? "Diagnosing…" : "Run local diagnostics"}
        </button>
      </div>

      {error && (
        <p className="mt-4 text-sm text-rose-400">⚠ {error}</p>
      )}

      {diag && (
        <>
          {/* Environment profile — contextual network picture, informational
              only (no pass/fail). Sits above the verdict and checks. */}
          {diag.profile ? <EnvProfile profile={diag.profile} /> : null}

          {/* The verdict — the product's soul. Deliberately loud. */}
          <div
            className={`mt-5 rounded-xl border p-4 ${VERDICT_STYLES[diag.verdictKind].box}`}
          >
            <div className="text-[10px] font-semibold uppercase tracking-widest text-white/50">
              {VERDICT_STYLES[diag.verdictKind].tag}
            </div>
            <p
              className={`mt-1 text-lg font-semibold leading-snug ${VERDICT_STYLES[diag.verdictKind].text}`}
            >
              {diag.verdict}
            </p>
          </div>

          {/* Per-check breakdown */}
          <ul className="mt-4 grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
            {diag.checks.map((c, i) => (
              <li
                key={`${c.provider}-${c.check}-${i}`}
                className="flex items-start gap-2 rounded-lg bg-black/20 px-3 py-2"
              >
                <span>{DIAGNOSTIC_ICONS[c.status].icon}</span>
                <span className="min-w-0">
                  <span className="text-sm font-medium text-white">
                    {c.provider}{" "}
                    <span className="font-mono text-xs uppercase text-white/40">
                      {c.check}
                    </span>
                  </span>
                  <span className={`block text-xs ${DIAGNOSTIC_ICONS[c.status].text}`}>
                    {c.detail}
                  </span>
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-right text-[10px] text-white/30 tabular-nums">
            checked {new Date(diag.checkedAt).toLocaleTimeString()}
          </p>
        </>
      )}
    </section>
  );
}

// Contextual network picture: egress IP, DNS results, and network-layer RTT.
// Informational — never a pass/fail. "Network RTT" is deliberately labelled as
// distinct from the model response latency shown on the provider cards.
function EnvProfile({ profile }: { profile: EnvironmentProfile }) {
  return (
    <div className="mt-5 rounded-xl border border-white/10 bg-black/20 p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-white/50">
          Environment profile
        </h3>
        <span className="text-[10px] text-white/30">context · not pass/fail</span>
      </div>

      <div className="mt-2 text-sm">
        <span className="text-white/40">Network egress IP: </span>
        <span className="font-mono text-white/90">{profile.egressIp ?? "unknown"}</span>
      </div>

      <table className="mt-3 w-full text-left text-xs">
        <thead>
          <tr className="text-white/40">
            <th className="font-medium">Host</th>
            <th className="font-medium">DNS → IP</th>
            <th className="font-medium text-right">Network RTT</th>
          </tr>
        </thead>
        <tbody className="align-top">
          {profile.hosts.map((h) => (
            <tr key={h.host} className="border-t border-white/5">
              <td className="py-1.5 pr-2">
                <div className="text-white/80">{h.provider}</div>
                <div className="font-mono text-[10px] text-white/30">{h.host}</div>
              </td>
              <td className="py-1.5 pr-2 font-mono text-white/60">
                {h.resolvedIps?.length ? h.resolvedIps.join(", ") : "unknown"}
              </td>
              <td className="py-1.5 text-right font-mono tabular-nums text-white/80">
                {h.tcpRttMs != null ? `${h.tcpRttMs}ms` : "unknown"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[10px] text-white/30">
        Network RTT = time to open a TCP connection — distinct from a card&apos;s
        model response latency. Helps tell &ldquo;slow network&rdquo; from &ldquo;slow model&rdquo;.
      </p>
    </div>
  );
}
