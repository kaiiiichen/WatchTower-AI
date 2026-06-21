"use client";

import { useEffect, useState } from "react";
import type { HealthSnapshot } from "@/lib/types";
import ProviderCard from "@/components/ProviderCard";
import AlertBanner from "@/components/AlertBanner";
import CommunitySignals from "@/components/CommunitySignals";
import LocalDiagnostics from "@/components/LocalDiagnostics";
import DetectionGap from "@/components/DetectionGap";

const POLL_MS = 30_000;

export default function Dashboard() {
  const [snap, setSnap] = useState<HealthSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: HealthSnapshot = await res.json();
        if (active) {
          setSnap(data);
          setError(null);
        }
      } catch (e) {
        // Keep stale data visible while showing the error.
        if (active) setError(e instanceof Error ? e.message : "fetch failed");
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
    <main className="min-h-screen bg-[#0a0a0f] px-6 py-10 text-white">
      <div className="mx-auto max-w-5xl">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">🛰️ WatchTower AI</h1>
            <p className="mt-1 text-sm text-white/50">
              Flight radar for AI services — detect Claude / GPT / Gemini outages
              before the official status page does.
            </p>
          </div>
          <div className="text-right text-xs text-white/40">
            {error && (
              <div className="text-rose-400">⚠ {error}</div>
            )}
            {snap ? (
              <>
                <div>Last updated</div>
                <div className="tabular-nums">
                  {new Date(snap.updatedAt).toLocaleTimeString()}
                </div>
              </>
            ) : !error ? (
              <span>Connecting…</span>
            ) : null}
          </div>
        </header>

        {snap?.alerts.length ? (
          <section className="mt-8 space-y-3">
            {snap.alerts.map((a) => (
              <AlertBanner key={a.id} alert={a} />
            ))}
          </section>
        ) : null}

        <section className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {snap
            ? snap.providers.map((p) => <ProviderCard key={p.id} p={p} />)
            : [0, 1, 2, 3, 4, 5].map((i) => (
                <div
                  key={i}
                  className="h-56 animate-pulse rounded-2xl border border-white/10 bg-white/[0.03]"
                />
              ))}
        </section>

        <LocalDiagnostics />

        <DetectionGap />

        {snap?.community?.length ? (
          <CommunitySignals signals={snap.community} />
        ) : null}

        <footer className="mt-10 text-center text-xs text-white/30">
          Polling every {POLL_MS / 1000}s
          {snap?.source === "live"
            ? " · live data"
            : snap?.source === "mock"
              ? " · mock data"
              : null}
        </footer>
      </div>
    </main>
  );
}
