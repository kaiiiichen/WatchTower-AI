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

export function buildMockSnapshot(): Omit<HealthSnapshot, "source"> {
  // Gemini is intentionally "degraded" to exercise the alert/agent UI.
  const claude: ProviderHealth = {
    id: "claude",
    name: "Claude",
    status: "operational",
    healthScore: jitter(98, 4),
    latencyMs: jitter(820, 120),
    tokenRate: jitter(74, 8),
    qaCorrect: true,
    latencyHistory: makeHistory(820, 180),
  };

  const gpt: ProviderHealth = {
    id: "gpt",
    name: "GPT",
    status: "operational",
    healthScore: jitter(96, 5),
    latencyMs: jitter(910, 140),
    tokenRate: jitter(68, 8),
    qaCorrect: true,
    latencyHistory: makeHistory(910, 200),
  };

  const gemini: ProviderHealth = {
    id: "gemini",
    name: "Gemini",
    status: "degraded",
    healthScore: jitter(61, 8),
    latencyMs: jitter(2400, 500),
    tokenRate: jitter(31, 10),
    qaCorrect: Math.random() > 0.4,
    latencyHistory: makeHistory(2200, 900),
  };

  return {
    providers: [claude, gpt, gemini],
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
