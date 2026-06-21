import type { HealthSnapshot, LocalDiagnosis, ProviderHealth } from "./types";

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
  qaCorrect: boolean | (() => boolean);
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
    qaCorrect: typeof seed.qaCorrect === "function" ? seed.qaCorrect() : seed.qaCorrect,
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
    // Real-world case from the probe diagnosis: Gemini flagship returns HTTP 429
    // (daily quota exhausted). That's an ACCOUNT problem, not an outage — so it
    // renders as orange "Rate limited", never red "Down".
    id: "gemini", name: "Gemini", status: "rate_limited",
    baseHealth: 0, healthSpread: 0, baseLatency: 180, latencySpread: 40,
    baseTokenRate: 0, tokenRateSpread: 0, qaCorrect: false,
    historyLatency: 800, historySpread: 200,
  },
];

// Mock diagnosis for standalone dev. Local checks are all green, but the mock
// snapshot's Gemini is rate-limited — so the verdict is "account-side", NOT
// "all clear" (this is exactly the bug the verdict fix addresses).
export function buildMockDiagnosis(): LocalDiagnosis {
  const now = new Date().toISOString();
  const checks = (["Claude", "GPT", "Gemini"] as const).flatMap((provider) => [
    { provider, check: "dns", status: "pass" as const, detail: "resolved host" },
    { provider, check: "tcp", status: "pass" as const, detail: "connected to :443" },
    { provider, check: "key", status: "pass" as const, detail: "key valid (HTTP 200)" },
  ]);
  return {
    checks,
    localHealthy: true,
    verdictKind: "account-side",
    verdict:
      "Your environment is fine — but Gemini (quota/rate limit) is on your account layer (quota/config), NOT a service outage.",
    checkedAt: now,
    profile: {
      egressIp: "203.0.113.42",
      hosts: [
        { provider: "Claude", host: "api.anthropic.com", resolvedIps: ["160.79.104.10"], tcpRttMs: 38 },
        { provider: "GPT", host: "api.openai.com", resolvedIps: ["104.18.6.192", "104.18.7.192"], tcpRttMs: 52 },
        { provider: "Gemini", host: "generativelanguage.googleapis.com", resolvedIps: ["142.250.80.10"], tcpRttMs: null },
      ],
    },
  };
}

export function buildMockSnapshot(): Omit<HealthSnapshot, "source"> {
  return {
    providers: PROVIDER_SEEDS.map(makeProvider),
    alerts: [
      {
        id: "alert-gemini-rate_limited",
        severity: "warning",
        providerId: "gemini",
        title: "Gemini flagship (gemini-3.1-pro-preview) is rate-limited",
        attribution:
          "Your account: Gemini returned HTTP 429 (rate/quota limit) for gemini-3.1-pro-preview — an account-side limit on your key, not a Gemini outage.",
        recoveryEta:
          "Clears when your rate/quota window resets — check your provider quota dashboard.",
        recommendedAlternative:
          "Route to Claude flagship (health 98, ~0.8s latency) while your quota resets.",
        insight:
          "Gemini flagship is rate-limited (HTTP 429): your account hit a request-rate or quota limit. This is your account's problem, NOT a Gemini service outage.",
        communityConfirmed: false,
        createdAt: new Date().toISOString(),
      },
    ],
    updatedAt: new Date().toISOString(),
    community: [
      {
        providerId: "Claude",
        subreddit: "ClaudeAI",
        status: "normal",
        complaintRate: 0.08,
        baseline: 0.07,
        postCount: 25,
        matchedPosts: 2,
        sampledAt: new Date().toISOString(),
      },
      {
        providerId: "GPT",
        subreddit: "OpenAI",
        status: "elevated",
        complaintRate: 0.2,
        baseline: 0.1,
        postCount: 25,
        matchedPosts: 5,
        sampledAt: new Date().toISOString(),
      },
      {
        // Coherent with the rate-limit above: a quota cap on YOUR key never
        // shows up as community chatter, so Gemini reads calm here.
        providerId: "Gemini",
        subreddit: "Bard",
        status: "normal",
        complaintRate: 0.08,
        baseline: 0.09,
        postCount: 25,
        matchedPosts: 2,
        sampledAt: new Date().toISOString(),
      },
    ],
  };
}
