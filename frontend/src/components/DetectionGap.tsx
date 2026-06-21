"use client";

import { useEffect, useState } from "react";
import type { BacktestReport, CaseTimeline, HistogramBin } from "@/lib/types";

// "Why WatchTower" — the Detection Gap. Argues from REAL VU-dataset numbers that
// official status pages lag/skip real-time acknowledgment, leaving a window that
// high-frequency probing fills. Every figure comes from the backend computation;
// the one estimated quantity (impact-window start) is explicitly flagged.
export default function DetectionGap() {
  const [rep, setRep] = useState<BacktestReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let on = true;
    fetch("/api/backtest", { cache: "no-store" })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: BacktestReport) => on && setRep(d))
      .catch((e) => on && setError(e instanceof Error ? e.message : "failed"));
    return () => {
      on = false;
    };
  }, []);

  if (error) {
    return (
      <section className="mt-10 rounded-2xl border border-white/10 bg-white/[0.03] p-6">
        <Header />
        <p className="mt-3 text-sm text-rose-400">⚠ backtest unavailable: {error}</p>
      </section>
    );
  }
  if (!rep) {
    return (
      <section className="mt-10 rounded-2xl border border-white/10 bg-white/[0.03] p-6">
        <Header />
        <div className="mt-4 h-40 animate-pulse rounded-xl bg-white/[0.03]" />
      </section>
    );
  }

  const cov = rep.coverage.all;
  const allRes = rep.latency.all.investigatingToResolved;
  const anthRes = rep.latency.anthropic.investigatingToResolved;
  const primary = rep.caseTimelines[0];
  const secondary = rep.caseTimelines[1];

  return (
    <section className="mt-10 rounded-2xl border border-white/10 bg-white/[0.03] p-6">
      <Header />

      {/* HOOK — coverage gap (100% real) */}
      <div className="mt-5 rounded-xl border border-rose-500/30 bg-rose-500/10 p-5">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="text-4xl font-bold tabular-nums text-rose-300">{fmt(cov.pct)}%</span>
          <span className="text-base font-medium text-white">
            of incidents were never marked “investigating” in real time
          </span>
        </div>
        <p className="mt-1 text-sm text-white/60">
          {cov.noInvestigating} of {cov.total} official incidents only ever got a
          “resolved” post — no live acknowledgment at all. The status page is blind
          while it happens.
        </p>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {/* CHART 1 — single real incident timeline */}
        {primary ? <CaseTimelineChart c={primary} secondary={secondary} /> : null}

        {/* CHART 2 — official response-latency distribution */}
        <HistogramChart
          bins={rep.resolvedHistogram}
          allMedian={allRes?.medianMin}
          anthMedian={anthRes?.medianMin}
          mean={allRes?.meanMin}
          n={allRes?.n}
          note={rep.histogramNote}
        />
      </div>

      {/* CONCLUSION — honest bridge, no overclaim */}
      <div className="mt-6 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
        <p className="text-sm leading-relaxed text-white/80">
          <span className="font-semibold text-emerald-300">The window WatchTower fills: </span>
          official pages skip real-time acknowledgment {fmt(cov.pct)}% of the time and,
          when they do post, take a median of {fmt(allRes?.medianMin ?? 0)} min to
          resolve. WatchTower probes every 30s with a QA quality check, so it can
          surface anomalies <em>inside</em> this acknowledgment window.
        </p>
        <p className="mt-2 text-xs text-white/40">
          Stated as the gap we can fill — not a claim of measured head-start (we have
          no historical probe data over these incidents).
        </p>
      </div>

      <p className="mt-4 text-[11px] text-white/30">
        Source: VU Amsterdam status-page dataset ({rep.datasetDate}). Coverage &
        latency are computed directly from official incident timestamps. Impact-window
        start in the case study is <strong>parsed from the official description text</strong>{" "}
        (date inferred from the incident&apos;s UTC day) — an estimate, flagged below.
      </p>
    </section>
  );
}

function Header() {
  return (
    <div>
      <h2 className="text-sm font-semibold uppercase tracking-widest text-white/50">
        Why WatchTower · Detection Gap
      </h2>
      <p className="mt-1 text-xs text-white/40">
        Official status pages confirm late — and sometimes not at all. Backtested on
        real VU Amsterdam data.
      </p>
    </div>
  );
}

// --- Chart 1: one incident's real timeline --------------------------------
function CaseTimelineChart({ c, secondary }: { c: CaseTimeline; secondary?: CaseTimeline }) {
  const t0 = ms(c.impactStart);
  const tInv = ms(c.investigating);
  const tEnd = ms(c.resolved) || tInv;
  const span = Math.max(1, tEnd - t0);
  const pos = (t: number) => `${((t - t0) / span) * 100}%`;

  return (
    <div className="rounded-xl border border-white/10 bg-black/20 p-4">
      <div className="text-xs font-medium text-white/60">
        Real incident · {c.provider} — “{c.title}”
      </div>

      <div className="relative mt-8 mb-10 h-1.5 rounded-full bg-white/10">
        {/* delayed-acknowledgment segment: impact start -> investigating */}
        <div
          className="absolute h-1.5 rounded-full bg-amber-400/70"
          style={{ left: pos(t0), width: pos(tInv) }}
        />
        <Marker left={pos(t0)} color="bg-amber-400" label="Impact start*" time={clock(c.impactStart)} above />
        <Marker left={pos(tInv)} color="bg-sky-400" label="Official investigating" time={clock(c.investigating)} />
        <Marker left="100%" color="bg-emerald-400" label="Resolved" time={clock(c.resolved)} above />
      </div>

      <div className="rounded-lg bg-amber-400/10 px-3 py-2 text-sm text-amber-200">
        Official status page delayed acknowledgment by{" "}
        <span className="font-bold tabular-nums">~{fmt(c.ackGapMin)} min</span>{" "}
        after users were already impacted.
      </div>
      {secondary ? (
        <p className="mt-2 text-xs text-white/40">
          A second case corroborates: “{secondary.title.slice(0, 38)}…” — ~{fmt(secondary.ackGapMin)} min delay.
        </p>
      ) : null}
      <p className="mt-2 text-[11px] text-white/30">
        * Impact window “{c.impactWindowText}” parsed from the official incident
        description (estimate).
      </p>
    </div>
  );
}

function Marker({
  left, color, label, time, above = false,
}: { left: string; color: string; label: string; time: string; above?: boolean }) {
  return (
    <div className="absolute -translate-x-1/2" style={{ left }}>
      <div className={`h-3 w-3 -translate-y-[3px] rounded-full ${color} ring-2 ring-black/40`} />
      <div className={`absolute ${above ? "bottom-4" : "top-4"} left-1/2 w-24 -translate-x-1/2 text-center`}>
        <div className="text-[10px] leading-tight text-white/60">{label}</div>
        <div className="font-mono text-[10px] tabular-nums text-white/40">{time}</div>
      </div>
    </div>
  );
}

// --- Chart 2: official response-latency distribution ----------------------
function HistogramChart({
  bins, allMedian, anthMedian, mean, n, note,
}: {
  bins: HistogramBin[];
  allMedian?: number; anthMedian?: number; mean?: number; n?: number; note: string;
}) {
  const maxCount = Math.max(1, ...bins.map((b) => b.count));
  return (
    <div className="rounded-xl border border-white/10 bg-black/20 p-4">
      <div className="text-xs font-medium text-white/60">
        Official internal response time (investigating → resolved)
      </div>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-3 text-sm">
        <span className="text-white/80">
          median <span className="font-bold tabular-nums text-white">{fmt(allMedian ?? 0)} min</span>
        </span>
        <span className="text-white/50">
          (Anthropic {fmt(anthMedian ?? 0)} min)
        </span>
        <span className="text-[11px] text-white/35">N={n}</span>
      </div>

      <div className="mt-3 space-y-1.5">
        {bins.map((b) => (
          <div key={b.label} className="flex items-center gap-2">
            <span className="w-16 shrink-0 text-right font-mono text-[10px] text-white/40">{b.label}</span>
            <div className="h-3 flex-1 rounded-sm bg-white/5">
              <div
                className="h-3 rounded-sm bg-sky-400/70"
                style={{ width: `${(b.count / maxCount) * 100}%` }}
              />
            </div>
            <span className="w-7 text-right font-mono text-[10px] tabular-nums text-white/50">{b.count}</span>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-white/30">
        Mean is {fmt(mean ?? 0)} min — skewed by a long tail (some incidents run for
        days), so the median is the honest headline. {note}
      </p>
    </div>
  );
}

// --- helpers ---------------------------------------------------------------
function ms(s?: string | null): number {
  if (!s) return NaN;
  return new Date(s.replace(" ", "T")).getTime();
}
function clock(s?: string | null): string {
  const t = ms(s);
  if (Number.isNaN(t)) return "—";
  return new Date(t).toISOString().slice(11, 16) + "Z";
}
function fmt(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}
