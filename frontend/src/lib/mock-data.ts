import type {
  BacktestReport,
  HealthSnapshot,
  LocalDiagnosis,
  ProviderHealth,
} from "./types";

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

// A steadily rising latency ramp — the visual signature of a "degrading" trend.
function makeRisingHistory(start: number, end: number, n = 20) {
  const now = Date.now();
  return Array.from({ length: n }, (_, i) => ({
    t: new Date(now - (n - 1 - i) * 30_000).toISOString(),
    ms: Math.max(50, Math.round(start + (end - start) * (i / (n - 1))) + jitter(0, 60)),
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
  rising?: boolean; // render a rising latency ramp (for "degrading")
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
    latencyHistory: seed.rising
      ? makeRisingHistory(seed.historyLatency * 0.45, seed.historyLatency)
      : makeHistory(seed.historyLatency, seed.historySpread),
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
    // Still healthy NOW (high score) but latency steadily climbing -> "degrading".
    id: "gpt", name: "GPT", status: "degrading",
    baseHealth: 90, healthSpread: 3, baseLatency: 1500, latencySpread: 80,
    baseTokenRate: 55, tokenRateSpread: 6, qaCorrect: true,
    historyLatency: 1500, historySpread: 200, rising: true,
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

// Detection lead-time backtest — the EXACT numbers the backend computes from the
// VU Amsterdam dataset (verified equal to backend output). Used for standalone
// dev; never re-rounded so the figures stay truthful.
export function buildMockBacktest(): BacktestReport {
  return {
    datasetDate: "2024-08-31",
    coverage: {
      all: { scope: "all", total: 542, noInvestigating: 161, pct: 29.7 },
      anthropic: { scope: "anthropic", total: 141, noInvestigating: 45, pct: 31.9 },
      openai: { scope: "openai", total: 365, noInvestigating: 106, pct: 29.0 },
    },
    latency: {
      all: {
        investigatingToResolved: { n: 381, medianMin: 73.0, meanMin: 163.8, p25Min: 31.0, p75Min: 164.0, maxMin: 4907.0 },
        investigatingToIdentified: { n: 126, medianMin: 27.5, meanMin: 50.2, p25Min: 9.0, p75Min: 59.0, maxMin: 588.0 },
      },
      anthropic: {
        investigatingToResolved: { n: 96, medianMin: 55.5, meanMin: 144.5, p25Min: 20.0, p75Min: 109.5, maxMin: 3030.0 },
        investigatingToIdentified: { n: 36, medianMin: 23.0, meanMin: 65.5, p25Min: 7.0, p75Min: 57.8, maxMin: 588.0 },
      },
      openai: {
        investigatingToResolved: { n: 259, medianMin: 78.0, meanMin: 169.0, p25Min: 35.0, p75Min: 171.0, maxMin: 4907.0 },
        investigatingToIdentified: { n: 84, medianMin: 31.5, meanMin: 45.5, p25Min: 13.0, p75Min: 62.8, maxMin: 225.0 },
      },
    },
    resolvedHistogram: [
      { label: "0-15m", count: 29 },
      { label: "15-30m", count: 59 },
      { label: "30-60m", count: 73 },
      { label: "60-120m", count: 97 },
      { label: "120-240m", count: 63 },
      { label: "240-480m", count: 41 },
      { label: "480m+", count: 19 },
    ],
    histogramNote:
      "investigating→resolved, all providers (N=381). Final bin absorbs the long tail.",
    caseTimelines: [
      {
        incidentId: "787xfxkthx3c",
        provider: "anthropic",
        title: "Elevated errors rates on API",
        impactWindowText: "15:38–16:29",
        impactStart: "2024-08-13T15:38:00+00:00",
        investigating: "2024-08-13T16:01:00+00:00",
        identified: "",
        resolved: "2024-08-13 16:32:00+00:00",
        ackGapMin: 23.0,
        impactStartEstimated: true,
      },
      {
        incidentId: "6l0r96skc6cb",
        provider: "anthropic",
        title: "Additional Rate Limits are being applied for API customers",
        impactWindowText: "19:01–19:12",
        impactStart: "2024-08-01T19:01:00+00:00",
        investigating: "2024-08-01T19:33:00+00:00",
        identified: "2024-08-01 19:46:00+00:00",
        resolved: "2024-08-01 21:21:00+00:00",
        ackGapMin: 32.0,
        impactStartEstimated: true,
      },
    ],
    notes: {
      A: "Official internal response latency — real. Median is the headline; mean is long-tail-skewed.",
      B: "Impact window parsed from official incident description text; date inferred from the incident's UTC day — an ESTIMATE.",
      C: "Coverage gap — 100% real, no estimation.",
    },
  };
}

export function buildMockSnapshot(): Omit<HealthSnapshot, "source"> {
  return {
    providers: PROVIDER_SEEDS.map(makeProvider),
    alerts: [
      {
        id: "alert-gpt-degrading",
        severity: "info",
        providerId: "gpt",
        title: "GPT flagship (gpt-5) performance is trending down",
        attribution:
          "Early-warning trend, not a fault yet — latency has climbed ~120% over the last 5 probes (680→1500ms) while still responding. Predicted from the live latency curve, before any outage.",
        recoveryEta: "Predictive — no incident yet; watching the trend.",
        recommendedAlternative:
          "Pre-warm Claude flagship (claude-opus-4-8) in case this continues.",
        insight:
          "⚠️ GPT flagship is steadily degrading and may be heading toward a problem. Latency keeps climbing while it still responds — a pre-emptive heads-up from the real-time trend, no incident has occurred yet.",
        communityConfirmed: false,
        officialAcknowledged: false,
        createdAt: new Date().toISOString(),
      },
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
        officialAcknowledged: false,
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
    official: [
      {
        providerId: "Claude",
        status: "operational",
        pageUrl: "https://status.claude.com/",
        active: false,
        sampledAt: new Date().toISOString(),
      },
      {
        providerId: "GPT",
        status: "operational",
        pageUrl: "https://status.openai.com/",
        active: false,
        sampledAt: new Date().toISOString(),
      },
      {
        providerId: "Gemini",
        status: "unavailable",
        pageUrl: "https://aistudio.google.com/status",
        active: false,
      },
    ],
  };
}
