"use client";

import { useEffect, useState } from "react";
import type { HealthSnapshot } from "@/lib/types";
import { SEMANTIC_COLORS, typeLgLight, typeMd, typeSm } from "@/lib/style-maps";
import ProviderCard from "@/components/ProviderCard";
import AlertBanner from "@/components/AlertBanner";
import CommunitySignals from "@/components/CommunitySignals";
import OfficialStatus from "@/components/OfficialStatus";
import LocalDiagnostics from "@/components/LocalDiagnostics";
import DetectionGap from "@/components/DetectionGap";
import MeasurementScope from "@/components/MeasurementScope";

const POLL_MS = 30_000;

export default function Dashboard() {
  const [snap, setSnap] = useState<HealthSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        if (!res.ok) {
          const body = (await res.json().catch(() => null)) as { error?: string } | null;
          throw new Error(body?.error ?? `HTTP ${res.status}`);
        }
        const data: HealthSnapshot = await res.json();
        if (active) {
          setSnap(data);
          setError(null);
        }
      } catch (e) {
        if (active) {
          setSnap(null);
          setError(e instanceof Error ? e.message : "Backend offline");
        }
      }
    }
    load();
    const id = setInterval(load, POLL_MS);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="max-w-[1180px] mx-auto px-4 md:px-12 py-16 space-y-14">
      <header className="flex flex-wrap items-start justify-between gap-4 fade-up" style={{ animationDelay: "0ms" }}>
        <div>
          <h1
            style={{ ...typeLgLight, letterSpacing: "-0.02em" }}
            className="text-zinc-900 dark:text-zinc-100"
          >
            Flight radar for AI services
          </h1>
          <p style={typeMd} className="mt-3 text-zinc-500 dark:text-zinc-500 max-w-2xl">
            Detect Claude / GPT / Gemini outages before the official status page
            does — real requests from your account, not a global oracle.
          </p>
        </div>
        <div style={typeSm} className="text-right text-zinc-400 dark:text-zinc-500 shrink-0 space-y-1">
          {error && <div className={SEMANTIC_COLORS.rose.text}>⚠ {error}</div>}
          {snap ? (
            <>
              <div>Last updated</div>
              <div className="tabular-nums text-zinc-600 dark:text-zinc-400">
                {new Date(snap.updatedAt).toLocaleTimeString()}
              </div>
            </>
          ) : !error ? (
            <span>Connecting…</span>
          ) : null}
          <div className="text-zinc-400 dark:text-zinc-500">
            Polling every {POLL_MS / 1000}s
            {snap ? " · live data" : null}
          </div>
        </div>
      </header>

      <section className="fade-up space-y-6" style={{ animationDelay: "40ms" }}>
        <div>
          <div className="mag-label">Providers</div>
          {error ? (
            <div className={`mag-card ${SEMANTIC_COLORS.rose.inset}`}>
              <p style={typeMd} className={SEMANTIC_COLORS.rose.text}>
                Backend offline — start the FastAPI server and set{" "}
                <code className="font-mono text-sm">BACKEND_URL</code>.
              </p>
            </div>
          ) : (
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {snap
                ? snap.providers.map((p) => <ProviderCard key={p.id} p={p} />)
                : [0, 1, 2, 3, 4, 5].map((i) => (
                    <div
                      key={i}
                      className="mag-card h-56 animate-pulse bg-zinc-100 dark:bg-zinc-800/50"
                    />
                  ))}
            </div>
          )}
        </div>

        {snap?.alerts.length ? (
          <div className="space-y-4">
            <div className="mag-label">Alerts</div>
            {snap.alerts.map((a) => (
              <AlertBanner key={a.id} alert={a} />
            ))}
          </div>
        ) : null}

        {snap?.official?.length ? (
          <div className="fade-up" style={{ animationDelay: "45ms" }}>
            <OfficialStatus signals={snap.official} />
          </div>
        ) : null}

        {snap?.community?.length ? (
          <div className="fade-up" style={{ animationDelay: "50ms" }}>
            <CommunitySignals signals={snap.community} />
          </div>
        ) : null}
      </section>

      <div className="fade-up" style={{ animationDelay: "60ms" }}>
        <LocalDiagnostics />
      </div>

      <div className="fade-up" style={{ animationDelay: "100ms" }}>
        <DetectionGap />
      </div>

      <div className="fade-up" style={{ animationDelay: "120ms" }}>
        <MeasurementScope />
      </div>
    </div>
  );
}
