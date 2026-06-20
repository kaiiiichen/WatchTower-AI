// Shared shapes for Watchtower AI dashboard.
// These mirror what the FastAPI backend will eventually return, so swapping
// the mock route for the real backend is a no-op on the frontend.

// "unknown" = provider not probed (e.g. API key missing) — never a crash.
export type ProviderStatus = "operational" | "degraded" | "down" | "unknown";

// Probed tier: "flagship" (strongest model) vs "mid" (mid model).
export type ProviderTier = "flagship" | "mid";

export interface ProviderHealth {
  id: string; // "claude-flagship" | "claude-mid" | "gpt-flagship" | ...
  name: string;
  status: ProviderStatus;
  healthScore: number; // 0-100
  latencyMs: number; // last probe latency
  tokenRate: number; // tokens/sec generation speed
  qaCorrect: boolean; // standard QA probe answered correctly
  latencyHistory: { t: string; ms: number }[]; // recent probes for the chart
  tier?: ProviderTier; // which tier this card represents
  model?: string; // the actual model id that was probed
}

export type AlertSeverity = "info" | "warning" | "critical";

export interface Alert {
  id: string;
  severity: AlertSeverity;
  providerId: string;
  title: string;
  // The "Agent" action chain output:
  attribution: string; // 1. whose problem
  recoveryEta: string; // 2. estimated recovery
  recommendedAlternative: string; // 3. healthiest alternative
  insight: string; // 4. LLM plain-language insight
  createdAt: string;
}

export type DataSource = "live" | "mock";

export interface HealthSnapshot {
  providers: ProviderHealth[];
  alerts: Alert[];
  updatedAt: string;
  source: DataSource;
}
