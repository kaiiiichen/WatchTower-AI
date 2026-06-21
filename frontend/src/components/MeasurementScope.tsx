"use client";

import { useState } from "react";
import { SEMANTIC_COLORS, typeLg, typeMd, typeSm } from "@/lib/style-maps";
import MagChip from "./mag-chip";

export default function MeasurementScope() {
  const [expanded, setExpanded] = useState(false);

  return (
    <section>
      <div className="mag-label">A local vantage-point monitor</div>
      <div className="mag-card">
        <p style={typeMd} className="text-zinc-700 dark:text-zinc-300 max-w-3xl">
          WatchTower runs on your machine with your API keys — not a shared cloud
          oracle. Every probe is a real request from your account, routed through
          whichever data center the provider sends you to. It reports{" "}
          <span className="font-semibold text-zinc-900 dark:text-zinc-100">
            your vantage point
          </span>{" "}
          — is it you or is it them, from where you sit — which is exactly what you
          need to decide to retry or fail over.
        </p>

        <div className={`mt-5 mag-card-inset ${SEMANTIC_COLORS.rose.inset}`}>
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span style={typeLg} className={SEMANTIC_COLORS.rose.textStrong}>
              Not a global oracle
            </span>
          </div>
          <p style={typeMd} className="mt-2 text-zinc-600 dark:text-zinc-400">
            We deliberately don&apos;t claim to know whether an outage is worldwide.
            A fault here might be your region, your key, or your route — local
            diagnostics help you tell.
          </p>
        </div>

        <div className={`mt-4 mag-card-inset ${SEMANTIC_COLORS.amber.inset}`}>
          <p style={typeMd} className={SEMANTIC_COLORS.amber.textOnTint}>
            <span className={`font-semibold ${SEMANTIC_COLORS.amber.textEmphasis}`}>
              Your route, your account:{" "}
            </span>
            end-to-end experience through whatever path the provider gives you — not
            a synthetic check from our infrastructure. That&apos;s the signal that matters
            for retry, failover, and paging.
          </p>
        </div>

        <div className={`mt-4 mag-card-inset ${SEMANTIC_COLORS.emerald.inset}`}>
          <p style={typeMd} className="text-zinc-700 dark:text-zinc-300">
            <span className={`font-semibold ${SEMANTIC_COLORS.emerald.textEmphasis}`}>
              Community signal is our breadth check:{" "}
            </span>
            when our probe sees a fault and Hacker News outage chatter is spiking,
            that&apos;s corroboration it&apos;s widespread — not just your route.
          </p>
          <p style={typeSm} className="mt-2 text-zinc-500 dark:text-zinc-500">
            Community never blocks core detection; it upgrades confidence when many
            people are reporting the same thing.
          </p>
        </div>

        <div className="mt-4">
          <MagChip
            as="button"
            size="sm"
            arrow={expanded ? "left" : "right"}
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
          >
            {expanded ? "Hide" : "Why vantage-point beats a global check"}
          </MagChip>

          {expanded ? (
            <div className="mt-3 mag-card-inset">
              <p style={typeMd} className="text-zinc-600 dark:text-zinc-400">
                Official status pages are slow and rarely tell you whether{" "}
                <em>your</em>{" "}
                API key, DNS, or region is the problem. A global uptime
                monitor from a vendor&apos;s own edge doesn&apos;t either — it measures their
                network, not yours.
              </p>
              <p style={typeMd} className="mt-3 text-zinc-600 dark:text-zinc-400">
                WatchTower runs from where you run it, with your credentials, on the
                same paths your app uses. That&apos;s the signal that matters for retry,
                failover, and paging — and why we pair it with community corroboration
                instead of pretending to be an outage oracle.
              </p>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
