"""Pydantic models whose field names match frontend/src/lib/types.ts exactly
(camelCase)."""
from typing import Literal

from pydantic import BaseModel

# "down" is reserved for genuine SERVICE faults (5xx / timeout). Account/config
# faults are split out so the product can answer "your problem vs the service's":
#   rate_limited  -> 429: your account hit a rate/quota limit
#   misconfigured -> other 4xx: model unavailable to your key, or key/permission
# "degrading" = a precursor/trend warning: still healthy NOW, but latency is
# steadily climbing (predicted to worsen). Distinct from "degraded" (already
# impaired). See probes.latency_trend.
ProviderStatus = Literal[
    "operational", "degrading", "degraded", "down", "unknown",
    "rate_limited", "misconfigured",
]
ProviderTier = Literal["flagship", "mid"]
AlertSeverity = Literal["info", "warning", "critical"]


class LatencyPoint(BaseModel):
    t: str  # ISO timestamp
    ms: int


class ProviderHealth(BaseModel):
    id: str
    name: str
    status: ProviderStatus
    healthScore: int
    latencyMs: int
    tokenRate: int
    qaCorrect: bool
    latencyHistory: list[LatencyPoint]
    tier: ProviderTier | None = None
    model: str | None = None


class Alert(BaseModel):
    id: str
    severity: AlertSeverity
    providerId: str
    title: str
    attribution: str
    recoveryEta: str
    recommendedAlternative: str
    insight: str
    createdAt: str
    # True when a community-signal spike corroborates this probe anomaly,
    # upgrading the alert to a "confirmed widespread event".
    communityConfirmed: bool = False
    officialAcknowledged: bool = False
    fusionMode: str | None = None


# Hacker News community-signal heat for a provider. "unavailable" = the source
# couldn't be reached this cycle — corroboration only, never blocks detection.
CommunitySignalStatus = Literal["normal", "elevated", "spike", "unavailable"]


class CommunitySignal(BaseModel):
    providerId: str  # provider name this signal corroborates (e.g. "Claude")
    source: str = "hackernews"
    searchQuery: str | None = None
    lookbackHours: int = 24
    status: CommunitySignalStatus
    complaintRate: float  # matched / total posts this cycle (0.0 when unavailable)
    baseline: float  # rolling mean complaint rate
    postCount: int
    matchedPosts: int
    sampledAt: str | None = None
    # Per-source corroboration entries (HN + optional Downdetector, etc.).
    sources: list[dict] = []


OfficialSignalStatus = Literal[
    "operational",
    "degraded",
    "partial_outage",
    "major_outage",
    "maintenance",
    "unavailable",
]


class OfficialStatusSignal(BaseModel):
    providerId: str
    status: OfficialSignalStatus
    headline: str | None = None
    latestUpdate: str | None = None
    latestPhase: str | None = None
    impactLabel: str | None = None
    componentSummary: str | None = None
    pageUrl: str
    active: bool = False
    sampledAt: str | None = None


# --- Local environment diagnostics ----------------------------------------
DiagnosticStatus = Literal["pass", "fail", "unknown"]
# your-side:    a local check failed (DNS/TCP/key) — your environment.
# account-side: local clean, but a provider is rate_limited/misconfigured —
#               your account layer (quota/config), not a service outage.
# service-side: local clean, but a provider is down/degraded — the provider's fault.
# all-clear:    local clean AND every provider operational.
# indeterminate: couldn't determine.
VerdictKind = Literal[
    "your-side", "account-side", "service-side", "all-clear", "indeterminate"
]


class DiagnosticCheck(BaseModel):
    provider: str
    check: str  # "dns" | "tcp" | "key"
    status: DiagnosticStatus
    detail: str


class HostNetInfo(BaseModel):
    provider: str
    host: str
    resolvedIps: list[str] | None = None  # DNS result (None = unknown)
    tcpRttMs: int | None = None  # NETWORK round-trip, distinct from model latency


class EnvironmentProfile(BaseModel):
    """Contextual network picture — informational, never affects the verdict."""
    egressIp: str | None = None
    hosts: list[HostNetInfo] = []


class LocalDiagnosis(BaseModel):
    checks: list[DiagnosticCheck]
    localHealthy: bool | None  # True=all pass, False=a fail, None=inconclusive
    verdictKind: VerdictKind
    verdict: str  # the headline attribution sentence
    checkedAt: str
    profile: EnvironmentProfile | None = None  # network environment context


# --- Detection lead-time backtest (VU Amsterdam dataset) -------------------
class StageStat(BaseModel):
    n: int
    medianMin: float
    meanMin: float  # long-tail-skewed — labelled as such in the UI
    p25Min: float
    p75Min: float
    maxMin: float


class ProviderLatency(BaseModel):
    investigatingToResolved: StageStat | None = None
    investigatingToIdentified: StageStat | None = None


class CoverageStat(BaseModel):
    scope: str
    total: int
    noInvestigating: int  # incidents never marked "investigating" in real time
    pct: float


class HistogramBin(BaseModel):
    label: str
    count: int


class CaseTimeline(BaseModel):
    incidentId: str
    provider: str
    title: str
    impactWindowText: str  # the raw "HH:MM-HH:MM" from the official description
    impactStart: str  # ISO — ESTIMATE (parsed from text, date inferred)
    investigating: str
    identified: str | None = None
    resolved: str | None = None
    ackGapMin: float
    impactStartEstimated: bool  # always True; surfaces the estimate in the UI


class BacktestReport(BaseModel):
    datasetDate: str
    coverage: dict[str, CoverageStat]
    latency: dict[str, ProviderLatency]
    resolvedHistogram: list[HistogramBin]
    histogramNote: str
    caseTimelines: list[CaseTimeline]
    notes: dict[str, str]


DataSource = Literal["live"]


class HealthSnapshot(BaseModel):
    providers: list[ProviderHealth]
    alerts: list[Alert]
    updatedAt: str
    source: DataSource | None = None
    community: list[CommunitySignal] = []
    official: list[OfficialStatusSignal] = []
