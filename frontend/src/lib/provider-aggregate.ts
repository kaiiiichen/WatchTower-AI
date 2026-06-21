import type {
  Alert,
  CommunitySignal,
  OfficialStatusSignal,
  ProviderHealth,
  ProviderStatus,
} from "./types";

export const PROVIDER_NAMES = ["Claude", "GPT", "Gemini"] as const;
export type ProviderName = (typeof PROVIDER_NAMES)[number];

export interface ProviderGroup {
  name: ProviderName;
  baseId: string;
  tiers: ProviderHealth[];
  primary: ProviderHealth;
  flagship?: ProviderHealth;
  mid?: ProviderHealth;
}

const STATUS_RANK: Record<ProviderStatus, number> = {
  down: 6,
  degraded: 5,
  misconfigured: 4,
  rate_limited: 3,
  degrading: 2,
  unknown: 1,
  operational: 0,
};

function pickPrimaryProbe(tiers: ProviderHealth[]): ProviderHealth {
  return tiers.reduce((worst, cur) =>
    STATUS_RANK[cur.status] > STATUS_RANK[worst.status] ? cur : worst
  );
}

export function groupProvidersByName(providers: ProviderHealth[]): ProviderGroup[] {
  const byName = new Map<string, ProviderHealth[]>();
  for (const p of providers) {
    const list = byName.get(p.name) ?? [];
    list.push(p);
    byName.set(p.name, list);
  }

  const groups: ProviderGroup[] = [];
  for (const name of PROVIDER_NAMES) {
    const tiers = byName.get(name) ?? [];
    if (!tiers.length) continue;
    const flagship =
      tiers.find((t) => t.tier === "flagship") ??
      tiers.find((t) => !t.id.endsWith("-mid")) ??
      tiers[0];
    const mid = tiers.find((t) => t.tier === "mid" || t.id.endsWith("-mid"));
    groups.push({
      name,
      baseId: flagship.id.split("-")[0],
      tiers,
      primary: pickPrimaryProbe(tiers),
      flagship,
      mid,
    });
  }
  return groups;
}

export function findOfficial(
  name: string,
  official?: OfficialStatusSignal[]
): OfficialStatusSignal | undefined {
  return official?.find((s) => s.providerId === name);
}

export function findCommunity(
  name: string,
  community?: CommunitySignal[]
): CommunitySignal | undefined {
  return community?.find((s) => s.providerId === name);
}

export function findAlertsForProvider(
  group: ProviderGroup,
  alerts: Alert[]
): Alert[] {
  const base = group.baseId.toLowerCase();
  const name = group.name.toLowerCase();
  return alerts.filter((a) => {
    const pid = a.providerId.toLowerCase();
    return pid === base || pid === name || pid.startsWith(`${base}-`);
  });
}

type SignalLevel = "clear" | "warn" | "bad" | "unknown";

function probeLevel(status: ProviderStatus): SignalLevel {
  if (status === "operational") return "clear";
  if (status === "degrading" || status === "rate_limited" || status === "misconfigured")
    return "warn";
  if (status === "unknown") return "unknown";
  return "bad";
}

function officialLevel(status: OfficialStatusSignal["status"]): SignalLevel {
  if (status === "operational") return "clear";
  if (status === "unavailable") return "unknown";
  if (status === "maintenance" || status === "degraded") return "warn";
  return "bad";
}

function communityLevel(status: CommunitySignal["status"]): SignalLevel {
  if (status === "normal") return "clear";
  if (status === "elevated") return "warn";
  if (status === "unavailable") return "unknown";
  return "bad";
}

export type CorroborationVerdict =
  | "aligned_clear"
  | "aligned_incident"
  | "probe_ahead"
  | "official_only"
  | "community_spike"
  | "account_local"
  | "split";

export interface CorroborationSummary {
  verdict: CorroborationVerdict;
  label: string;
  detail: string;
  hue: "emerald" | "amber" | "rose" | "sky" | "zinc";
}

export function summarizeCorroboration(
  probe: ProviderHealth,
  official?: OfficialStatusSignal,
  community?: CommunitySignal
): CorroborationSummary {
  const p = probeLevel(probe.status);
  const o = official ? officialLevel(official.status) : "unknown";
  const c = community ? communityLevel(community.status) : "unknown";

  if (probe.status === "rate_limited" || probe.status === "misconfigured") {
    return {
      verdict: "account_local",
      label: "Account-local",
      detail: "Probe sees your key/quota — official & community often stay calm.",
      hue: "amber",
    };
  }

  const probeBad = p === "bad" || p === "warn";
  const officialBad = o === "bad" || o === "warn";
  const communityBad = c === "bad" || c === "warn";

  if (!probeBad && !officialBad && !communityBad) {
    return {
      verdict: "aligned_clear",
      label: "Aligned",
      detail: "Probe, official page, and HN all clear.",
      hue: "emerald",
    };
  }

  if (probeBad && officialBad && (communityBad || c === "unknown")) {
    return {
      verdict: "aligned_incident",
      label: "Corroborated",
      detail: "Multiple signals agree something is wrong.",
      hue: "rose",
    };
  }

  if (probeBad && !officialBad && !communityBad) {
    return {
      verdict: "probe_ahead",
      label: "Probe ahead",
      detail: "Your probe sees a fault before official or community reacts.",
      hue: "amber",
    };
  }

  if (!probeBad && officialBad) {
    return {
      verdict: "official_only",
      label: "Official only",
      detail: "Status page reports an issue your probe hasn't hit yet.",
      hue: "sky",
    };
  }

  if (!probeBad && communityBad) {
    return {
      verdict: "community_spike",
      label: "HN chatter",
      detail: "Community spike without a probe fault — watch closely.",
      hue: "amber",
    };
  }

  return {
    verdict: "split",
    label: "Mixed signals",
    detail: "Sources disagree — open detail for attribution.",
    hue: "zinc",
  };
}
