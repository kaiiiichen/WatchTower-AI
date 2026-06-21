"use client";

import { useState } from "react";
import type { EnvironmentProfile, LocalDiagnosis } from "@/lib/types";
import { DIAGNOSTIC_ICONS, SEMANTIC_COLORS, VERDICT_STYLES, monoSm, typeLg, typeMd, typeMdSemibold, typeSm, typeSmSemibold } from "@/lib/style-maps";
import MagChip from "./mag-chip";
import DiagnosticCheckHelp from "./diagnostic-check-help";

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
    <section>
      <div className="mag-label">Local diagnostics</div>
      <p style={typeMd} className="-mt-2 mb-4 text-zinc-400 dark:text-zinc-600 max-w-2xl">
        Official page still green? Check your side in seconds: DNS · TCP :443 · API key.
        Fast reassurance before you assume a global outage.
      </p>
      <div className="mag-card">
      <div className="flex flex-wrap justify-end gap-3">
        <MagChip as="button" onClick={run} disabled={loading}>
          {loading ? "Diagnosing…" : "Run diagnostics"}
        </MagChip>
      </div>

      {error && (
        <div className={`mt-4 mag-card-inset ${SEMANTIC_COLORS.rose.inset}`}>
          <p style={typeMd} className={SEMANTIC_COLORS.rose.text}>
            ⚠ {error}
          </p>
        </div>
      )}

      {!diag && !loading && !error ? (
        <div className="mt-4 mag-card-inset">
          <p style={typeMd} className="text-zinc-500 dark:text-zinc-500">
            Run diagnostics to see whether issues are on your side or the provider&apos;s.
          </p>
        </div>
      ) : null}

      {diag && (
        <>
          {diag.profile ? <EnvProfile profile={diag.profile} /> : null}

          {(() => {
            const v = VERDICT_STYLES[diag.verdictKind];
            return (
              <div className={`mt-4 mag-card-inset ${v.box}`}>
                <div className="flex items-center gap-2">
                  <span className={`h-2.5 w-2.5 rounded-full shrink-0 ${v.dot} animate-pulse`} />
                  <div
                    style={{ ...typeSmSemibold, letterSpacing: "0.12em" }}
                    className={`uppercase ${v.text}`}
                  >
                    {v.tag}
                  </div>
                </div>
                <p
                  style={typeLg}
                  className={`mt-1 ${v.text}`}
                >
                  {diag.verdict}
                </p>
              </div>
            );
          })()}

          <ul className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {diag.checks.map((c, i) => {
              const icon = DIAGNOSTIC_ICONS[c.status];
              return (
              <li key={`${c.provider}-${c.check}-${i}`} className="mag-card-inset !p-3 flex items-start gap-2">
                {icon.icon ? (
                  <span>{icon.icon}</span>
                ) : (
                  <span className={`mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full ${icon.dot} animate-pulse`} />
                )}
                <span className="min-w-0 flex-1">
                  <span
                    style={typeMdSemibold}
                    className="inline-flex flex-wrap items-center gap-1.5 text-zinc-800 dark:text-zinc-200"
                  >
                    {c.provider}{" "}
                    <span
                      className="uppercase text-zinc-400 dark:text-zinc-500"
                      style={monoSm}
                    >
                      {c.check}
                    </span>
                    <DiagnosticCheckHelp check={c.check} />
                  </span>
                  <span
                    style={typeSm}
                    className={`block ${icon.text}`}
                  >
                    {c.detail}
                  </span>
                </span>
              </li>
              );
            })}
          </ul>
          <p
            style={typeSm}
            className="mt-3 text-right text-zinc-400 dark:text-zinc-500 tabular-nums"
          >
            checked {new Date(diag.checkedAt).toLocaleTimeString()}
          </p>
        </>
      )}
      </div>
    </section>
  );
}

function EnvProfile({ profile }: { profile: EnvironmentProfile }) {
  return (
    <div className="mt-4 mag-card-inset">
      <div className="flex items-baseline justify-between gap-2">
        <h3
          style={{ ...typeSmSemibold, letterSpacing: "0.1em" }}
          className="uppercase text-zinc-400 dark:text-zinc-500"
        >
          Environment profile
        </h3>
        <span style={typeSm} className="text-zinc-400 dark:text-zinc-500">
          context · not pass/fail
        </span>
      </div>

      <div style={typeMd} className="mt-2">
        <span className="text-zinc-500 dark:text-zinc-500">Network egress IP: </span>
        <span
          className="text-zinc-800 dark:text-zinc-200"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {profile.egressIp ?? "unknown"}
        </span>
      </div>

      <table style={typeSm} className="mt-3 w-full text-left">
        <thead>
          <tr className="text-zinc-400 dark:text-zinc-500">
            <th className="font-medium">Host</th>
            <th className="font-medium">DNS → IP</th>
            <th className="font-medium text-right">Network RTT</th>
          </tr>
        </thead>
        <tbody className="align-top">
          {profile.hosts.map((h) => (
            <tr key={`${h.provider}-${h.host}`} className="border-t border-zinc-200 dark:border-zinc-700">
              <td className="py-1.5 pr-2">
                <div className="text-zinc-700 dark:text-zinc-300">{h.provider}</div>
                <div
                  className="text-zinc-400 dark:text-zinc-500"
                  style={monoSm}
                >
                  {h.host}
                </div>
              </td>
              <td
                className="py-1.5 pr-2 text-zinc-600 dark:text-zinc-400"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                {h.resolvedIps?.length ? h.resolvedIps.join(", ") : "unknown"}
              </td>
              <td
                className="py-1.5 text-right tabular-nums text-zinc-700 dark:text-zinc-300"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                {h.tcpRttMs != null ? `${h.tcpRttMs}ms` : "unknown"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={typeSm} className="mt-2 text-zinc-400 dark:text-zinc-500">
        Network RTT = time to open a TCP connection — distinct from a card&apos;s model
        response latency.
      </p>
    </div>
  );
}
