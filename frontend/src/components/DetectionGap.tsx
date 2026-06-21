"use client";

import { useEffect, useState } from "react";
import type { BacktestReport, CaseTimeline, HistogramBin } from "@/lib/types";
import { SEMANTIC_COLORS, accentLink, monoSm, typeMd, typeMdSemibold, typeSm, typeStat } from "@/lib/style-maps";
import { DATASET_REPO, DATASET_URL, PAPER_URL } from "@/lib/research-foundation";

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
      <section>
        <SectionHead />
        <div className="mag-card !overflow-visible">
          <div className={`mag-card-inset ${SEMANTIC_COLORS.rose.inset}`}>
            <p style={typeMd} className={SEMANTIC_COLORS.rose.text}>
              ⚠ backtest unavailable: {error}
            </p>
          </div>
          <DatasetCredit />
        </div>
      </section>
    );
  }
  if (!rep) {
    return (
      <section>
        <SectionHead />
        <div className="mag-card !overflow-visible">
          <div className="mag-card-inset h-40 animate-pulse bg-zinc-100 dark:bg-zinc-800/50" />
          <DatasetCredit />
        </div>
      </section>
    );
  }

  const cov = rep.coverage.all;
  const allRes = rep.latency.all.investigatingToResolved;
  const anthRes = rep.latency.anthropic.investigatingToResolved;
  const primary = rep.caseTimelines[0];
  const secondary = rep.caseTimelines[1];

  return (
    <section>
      <SectionHead />
      <div className="mag-card !overflow-visible">
      <div className={`mag-card-inset ${SEMANTIC_COLORS.rose.inset}`}>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span
            style={typeStat}
            className={`tabular-nums ${SEMANTIC_COLORS.rose.textStrong}`}
          >
            {fmt(cov.pct)}%
          </span>
          <span style={typeMdSemibold} className="text-zinc-800 dark:text-zinc-200">
            of incidents were never marked “investigating” in real time
          </span>
        </div>
        <p style={typeMd} className="mt-2 text-zinc-600 dark:text-zinc-400">
          {cov.noInvestigating} of {cov.total} official incidents only ever got a
          “resolved” post — no live acknowledgment at all.
        </p>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2 lg:items-start">
        {primary ? <CaseTimelineChart c={primary} secondary={secondary} /> : null}
        <HistogramChart
          bins={rep.resolvedHistogram}
          allMedian={allRes?.medianMin}
          anthMedian={anthRes?.medianMin}
          mean={allRes?.meanMin}
          n={allRes?.n}
          note={rep.histogramNote}
        />
      </div>

      <div className={`mt-6 mag-card-inset ${SEMANTIC_COLORS.emerald.inset}`}>
        <p style={typeMd} className="text-zinc-700 dark:text-zinc-300">
          <span className={`font-semibold ${SEMANTIC_COLORS.emerald.textEmphasis}`}>
            The window WatchTower fills:{" "}
          </span>
          official pages skip real-time acknowledgment {fmt(cov.pct)}% of the time and,
          when they do post, take a median of {fmt(allRes?.medianMin ?? 0)} min to
          resolve. WatchTower probes every 30s with a QA quality check.
        </p>
        <p style={typeSm} className="mt-2 text-zinc-500 dark:text-zinc-500">
          Stated as the gap we can fill — not a claim of measured head-start.
        </p>
      </div>

      <DatasetCredit datasetDate={rep.datasetDate} />
      </div>
    </section>
  );
}

function SectionHead() {
  return (
    <>
      <div className="mag-label">Detection gap</div>
      <p style={typeMd} className="-mt-2 mb-4 text-zinc-400 dark:text-zinc-600">
        Official status pages confirm late — and sometimes not at all. Backtested on
        real VU Amsterdam data.
      </p>
    </>
  );
}

function DatasetCredit({ datasetDate }: { datasetDate?: string }) {
  return (
    <div className="mt-4 mag-card-inset">
      <p style={typeSm} className="text-zinc-400 dark:text-zinc-500">
        Source:{" "}
        <a href={PAPER_URL} target="_blank" rel="noopener noreferrer" className={accentLink}>
          Chu et al., ICPE&nbsp;2025
        </a>
        {" · "}
        <a href={DATASET_URL} target="_blank" rel="noopener noreferrer" className={accentLink}>
          Zenodo dataset
        </a>
        {" · "}
        <a href={DATASET_REPO} target="_blank" rel="noopener noreferrer" className={accentLink}>
          analysis code
        </a>
        {datasetDate ? <> · through {datasetDate}</> : null}. Impact-window start in the
        case study is parsed from the official description text — an estimate, flagged below.
      </p>
    </div>
  );
}

function CaseTimelineChart({ c, secondary }: { c: CaseTimeline; secondary?: CaseTimeline }) {
  const t0 = ms(c.impactStart);
  const tInv = ms(c.investigating);
  const tEnd = ms(c.resolved) || tInv;
  const span = Math.max(1, tEnd - t0);
  const pos = (t: number) => `${((t - t0) / span) * 100}%`;

  return (
    <div className="mag-card-inset !overflow-visible">
      <div style={typeMdSemibold} className="text-zinc-600 dark:text-zinc-400">
        Real incident · {c.provider} — “{c.title}”
      </div>

      {/* Tall shell so absolute marker labels stay inside the card (inset uses overflow:hidden). */}
      <div className="relative mt-4 px-10 pt-14 pb-14">
        <div className="relative h-1.5 rounded-full bg-zinc-200 dark:bg-zinc-700">
          <div
            className={`absolute h-1.5 rounded-full ${SEMANTIC_COLORS.amber.barSoft}`}
            style={{ left: 0, width: pos(tInv) }}
          />
          <Marker
            align="start"
            left={pos(t0)}
            color={SEMANTIC_COLORS.amber.dot}
            label="Impact start*"
            time={clock(c.impactStart)}
            above
          />
          <Marker
            align="center"
            left={pos(tInv)}
            color={SEMANTIC_COLORS.sky.dot}
            label="Official investigating"
            time={clock(c.investigating)}
          />
          <Marker
            align="end"
            left="100%"
            color={SEMANTIC_COLORS.emerald.dot}
            label="Resolved"
            time={clock(c.resolved)}
            above
          />
        </div>
      </div>

      <div
        style={typeMd}
        className={`rounded-md px-4 py-3 ${SEMANTIC_COLORS.amber.inset} ${SEMANTIC_COLORS.amber.textOnTint}`}
      >
        Official status page delayed acknowledgment by{" "}
        <span style={typeStat} className="tabular-nums align-baseline whitespace-nowrap">
          ~{fmt(c.ackGapMin)} min
        </span>{" "}
        after users were already impacted.
      </div>
      {secondary ? (
        <p style={typeSm} className="mt-2 text-zinc-500 dark:text-zinc-500">
          A second case corroborates: “{secondary.title.slice(0, 38)}…” — ~{fmt(secondary.ackGapMin)} min delay.
        </p>
      ) : null}
      <p style={typeSm} className="mt-2 text-zinc-400 dark:text-zinc-500">
        * Impact window “{c.impactWindowText}” parsed from the official incident description (estimate).
      </p>
    </div>
  );
}

function Marker({
  left,
  color,
  label,
  time,
  above = false,
  align = "center",
}: {
  left: string;
  color: string;
  label: string;
  time: string;
  above?: boolean;
  align?: "start" | "center" | "end";
}) {
  const positionClass =
    align === "start"
      ? "left-0"
      : align === "end"
        ? "right-0"
        : "-translate-x-1/2";

  const labelAnchor =
    align === "start"
      ? "left-0 text-left"
      : align === "end"
        ? "right-0 text-right"
        : "left-1/2 -translate-x-1/2 text-center";

  return (
    <div
      className={`absolute top-1/2 -translate-y-1/2 ${positionClass}`}
      style={align === "center" ? { left } : undefined}
    >
      <div className={`h-3 w-3 rounded-full ${color} ring-2 ring-[var(--background)]`} />
      <div
        className={`absolute w-28 ${above ? "bottom-5" : "top-5"} ${labelAnchor}`}
      >
        <div style={typeSm} className="leading-tight text-zinc-500 dark:text-zinc-400">
          {label}
        </div>
        <div style={monoSm} className="tabular-nums text-zinc-400 dark:text-zinc-500">
          {time}
        </div>
      </div>
    </div>
  );
}

function HistogramChart({
  bins,
  allMedian,
  anthMedian,
  mean,
  n,
  note,
}: {
  bins: HistogramBin[];
  allMedian?: number;
  anthMedian?: number;
  mean?: number;
  n?: number;
  note: string;
}) {
  const maxCount = Math.max(1, ...bins.map((b) => b.count));
  return (
    <div className="mag-card-inset">
      <div style={typeMdSemibold} className="text-zinc-600 dark:text-zinc-400">
        Official internal response time (investigating → resolved)
      </div>
      <div style={typeMd} className="mt-1 flex flex-wrap items-baseline gap-x-3">
        <span className="text-zinc-700 dark:text-zinc-300">
          median{" "}
          <span style={typeStat} className="tabular-nums text-zinc-900 dark:text-zinc-100">
            {fmt(allMedian ?? 0)} min
          </span>
        </span>
        <span className="text-zinc-500 dark:text-zinc-500">(Anthropic {fmt(anthMedian ?? 0)} min)</span>
        <span style={typeSm} className="text-zinc-400 dark:text-zinc-500">N={n}</span>
      </div>

      <div className="mt-3 space-y-1.5">
        {bins.map((b) => (
          <div key={b.label} className="flex items-center gap-2">
            <span
              className="w-16 shrink-0 text-right text-zinc-400 dark:text-zinc-500"
              style={monoSm}
            >
              {b.label}
            </span>
            <div className="h-3 flex-1 rounded-sm bg-zinc-100 dark:bg-zinc-800">
              <div
                className={`h-3 rounded-sm ${SEMANTIC_COLORS.sky.bar}`}
                style={{ width: `${(b.count / maxCount) * 100}%` }}
              />
            </div>
            <span
              className="w-7 text-right tabular-nums text-zinc-500 dark:text-zinc-400"
              style={monoSm}
            >
              {b.count}
            </span>
          </div>
        ))}
      </div>
      <p style={typeSm} className="mt-2 text-zinc-400 dark:text-zinc-500">
        Mean is {fmt(mean ?? 0)} min — skewed by a long tail. {note}
      </p>
    </div>
  );
}

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
