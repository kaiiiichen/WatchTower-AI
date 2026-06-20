import type { HealthSnapshot, ProviderHealth } from "./types";

// Deterministic-ish fake data generator for the walking skeleton.
// Produces a fresh snapshot each call so the 30s polling visibly updates.

function jitter(base: number, spread: number) {
  return Math.round(base + (Math.random() - 0.5) * spread);
}

function makeHistory(base: number, spread: number, n = 20) {
  const now = Date.now();
  return Array.from({ length: n }, (_, i) => ({
    t: new Date(now - (n - 1 - i) * 30_000).toISOString(),
    ms: Math.max(50, jitter(base, spread)),
  }));
}

interface ProviderSeed {
  id: string;
  name: string;
  status: ProviderHealth["status"];
  baseHealth: number;
  healthSpread: number;
  baseLatency: number;
  latencySpread: number;
  baseTokenRate: number;
  tokenRateSpread: number;
  qaCorrect: boolean;
  historyLatency: number;
  historySpread: number;
}

function makeProvider(seed: ProviderSeed): ProviderHealth {
  return {
    id: seed.id,
    name: seed.name,
    status: seed.status,
    healthScore: jitter(seed.baseHealth, seed.healthSpread),
    latencyMs: jitter(seed.baseLatency, seed.latencySpread),
    tokenRate: jitter(seed.baseTokenRate, seed.tokenRateSpread),
    qaCorrect: seed.qaCorrect,
    latencyHistory: makeHistory(seed.historyLatency, seed.historySpread),
  };
}

const PROVIDER_SEEDS: ProviderSeed[] = [
  {
    id: "claude", name: "Claude", status: "operational",
    baseHealth: 98, healthSpread: 4, baseLatency: 820, latencySpread: 120,
    baseTokenRate: 74, tokenRateSpread: 8, qaCorrect: true,
    historyLatency: 820, historySpread: 180,
  },
  {
    id: "gpt", name: "GPT", status: "operational",
    baseHealth: 96, healthSpread: 5, baseLatency: 910, latencySpread: 140,
    baseTokenRate: 68, tokenRateSpread: 8, qaCorrect: true,
    historyLatency: 910, historySpread: 200,
  },
  {
    id: "gemini", name: "Gemini", status: "degraded",
    baseHealth: 61, healthSpread: 8, baseLatency: 2400, latencySpread: 500,
    baseTokenRate: 31, tokenRateSpread: 10, qaCorrect: Math.random() > 0.4,
    historyLatency: 2200, historySpread: 900,
  },
];

export function buildMockSnapshot(): Omit<HealthSnapshot, "source"> {
  return {
    providers: PROVIDER_SEEDS.map(makeProvider),
    alerts: [
      {
        id: "alert-gemini-latency",
        severity: "warning",
        providerId: "gemini",
        title: "Gemini latency spike & QA degradation",
        attribution:
          "Cloud-side. Your network and local environment look healthy — 2 other providers respond normally from the same probe.",
        recoveryEta:
          "~25 min. Similar incidents in our history cleared within 18-32 min.",
        recommendedAlternative:
          "Route to Claude (health 98, ~0.8s latency) for the next ~30 min.",
        insight:
          "Gemini's response latency tripled and one QA probe failed, while Claude and GPT are nominal. This is consistent with a provider-side capacity issue, not a problem on your end. Failover recommended.",
        createdAt: new Date().toISOString(),
      },
    ],
    updatedAt: new Date().toISOString(),
  };
}
