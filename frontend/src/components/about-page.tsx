"use client";

import { useState } from "react";
import DetectionGap from "@/components/DetectionGap";
import MeasurementScope from "@/components/MeasurementScope";
import MagChip from "@/components/mag-chip";
import { SEMANTIC_COLORS, typeLgLight, typeMd, typeMdSemibold, typeSm } from "@/lib/style-maps";

const LAYERS = [
  {
    title: "Probe layer",
    hue: "sky" as const,
    body: "Every 30 seconds, real requests hit Claude, GPT, and Gemini through your API keys — with QA checks beyond HTTP 200, latency trends, and precursor warnings before status flips to degraded.",
  },
  {
    title: "Attribution layer",
    hue: "amber" as const,
    body: "Local diagnostics answer the 2 AM question: is it your DNS, your key, your route — or the provider? Four-way verdicts and smart alerts that never treat a 429 like a global outage.",
  },
  {
    title: "Corroboration",
    hue: "rose" as const,
    body: "Your probe, official status pages, and Hacker News sit side-by-side on the dashboard — aligned when they agree, flagged when they diverge. Community never blocks detection; it upgrades confidence.",
  },
];

export default function AboutPage() {
  const [showWhy, setShowWhy] = useState(false);

  return (
    <div className="max-w-[900px] space-y-12">
      <section className="mag-card">
        <p className="mag-label !mb-0 !static !transform-none text-[var(--accent)]">
          WatchTower AI
        </p>
        <h2
          style={{ ...typeLgLight, letterSpacing: "-0.02em" }}
          className="mt-3 text-zinc-900 dark:text-zinc-100"
        >
          Flight radar for AI services
        </h2>
        <p style={typeMd} className="mt-4 text-zinc-600 dark:text-zinc-400 max-w-2xl">
          WatchTower detects Claude, GPT, and Gemini outages before the official status page
          does — and tells you whether the problem is on your side or theirs. It runs locally
          on your machine: your API keys stay yours, probe history lives in SQLite, and nothing
          is uploaded to a shared cloud.
        </p>
        <p style={typeMd} className="mt-3 text-zinc-600 dark:text-zinc-400 max-w-2xl">
          The dashboard puts three signals on one card per provider — your probe, the official
          page, and HN chatter — so corroboration is visible at a glance, not buried in tabs.
        </p>
      </section>

      <section>
        <div className="mag-label">What WatchTower does</div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {LAYERS.map((layer) => {
            const c = SEMANTIC_COLORS[layer.hue];
            return (
              <div key={layer.title} className={`mag-card-inset ${c.inset}`}>
                <h3 style={typeMdSemibold} className={c.textEmphasis}>
                  {layer.title}
                </h3>
                <p style={typeSm} className="mt-2 text-zinc-600 dark:text-zinc-400">
                  {layer.body}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      <MeasurementScope />

      <section id="why-detection-gap">
        <MagChip
          as="button"
          size="sm"
          arrow={showWhy ? "left" : "right"}
          onClick={() => setShowWhy((v) => !v)}
          aria-expanded={showWhy}
        >
          {showWhy ? "Hide" : "Why detection gap?"} — research backtest
        </MagChip>
        {showWhy ? (
          <div className="mt-6">
            <DetectionGap />
          </div>
        ) : null}
      </section>
    </div>
  );
}
