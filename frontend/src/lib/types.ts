// Shared shapes for Watchtower AI dashboard.
// These mirror what the FastAPI backend will eventually return, so swapping
// the mock route for the real backend is a no-op on the frontend.

// "down" is reserved for genuine SERVICE outages (5xx / timeout). Account/config
// faults are split out so the UI answers "your problem vs the service's":
//   "rate_limited"  — 429: your account hit a rate/quota limit
//   "misconfigured" — other 4xx: model unavailable to your key, or key/permission
// "unknown" = provider not probed (e.g. API key missing) — never a crash.
export type ProviderStatus =
  | "operational"
  | "degraded"
  | "down"
  | "unknown"
  | "rate_limited"
  | "misconfigured";

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
  // True when a Reddit community-signal spike corroborates the probe anomaly,
  // upgrading the alert to a "confirmed widespread event".
  communityConfirmed?: boolean;
}

// Reddit community-signal heat for a provider. "unavailable" = source couldn't
// be reached this cycle — corroboration only, never blocks core detection.
export type CommunitySignalStatus =
  | "normal"
  | "elevated"
  | "spike"
  | "unavailable";

export interface CommunitySignal {
  providerId: string; // provider name this corroborates (e.g. "Claude")
  subreddit?: string | null;
  status: CommunitySignalStatus;
  complaintRate: number; // matched / total posts this cycle
  baseline: number; // rolling mean complaint rate
  postCount: number;
  matchedPosts: number;
  sampledAt?: string | null;
}

export type DataSource = "live" | "mock";

export interface HealthSnapshot {
  providers: ProviderHealth[];
  alerts: Alert[];
  updatedAt: string;
  source: DataSource;
  community?: CommunitySignal[];
}

// --- Local environment diagnostics ----------------------------------------
// Answers the product's core question: is the problem yours or the service's?
export type DiagnosticStatus = "pass" | "fail" | "unknown";
export type VerdictKind =
  | "your-side" // a local check failed
  | "service-side" // local clean, a provider is down
  | "all-clear" // everything healthy
  | "indeterminate"; // couldn't determine

export interface DiagnosticCheck {
  provider: string;
  check: string; // "dns" | "tcp" | "key"
  status: DiagnosticStatus;
  detail: string;
}

export interface LocalDiagnosis {
  checks: DiagnosticCheck[];
  localHealthy: boolean | null;
  verdictKind: VerdictKind;
  verdict: string; // the headline attribution sentence
  checkedAt: string;
}
