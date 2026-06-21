"use client";

import { useState } from "react";
import type { LocalDiagnosis } from "@/lib/types";
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
