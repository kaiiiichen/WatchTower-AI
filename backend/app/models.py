"""Pydantic models whose field names match frontend/src/lib/types.ts exactly
(camelCase). Serialized JSON is therefore a drop-in for the mock route."""
from typing import Literal

from pydantic import BaseModel

ProviderStatus = Literal["operational", "degraded", "down", "unknown"]
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


DataSource = Literal["live", "mock"]


class HealthSnapshot(BaseModel):
    providers: list[ProviderHealth]
    alerts: list[Alert]
    updatedAt: str
    source: DataSource | None = None
