"use client";

import type { ProviderGroup } from "@/lib/provider-aggregate";
import { summarizeCorroboration } from "@/lib/provider-aggregate";
import type { CommunitySignal, OfficialStatusSignal, ProviderHealth } from "@/lib/types";
import {
  COMMUNITY_STYLES,
  OFFICIAL_STYLES,
  STATUS_STYLES,
  monoSm,
  typeLg,
  typeMdSemibold,
  typeSm,
} from "@/lib/style-maps";
import LatencyChart from "./LatencyChart";
import CorroborationBadge from "./corroboration-badge";

type Props = {
  group: ProviderGroup;
  official?: OfficialStatusSignal;
  community?: CommunitySignal;
  onSelect: () => void;
};

export default function ProviderUnifiedCard({
  group,
  official,
  community,
  onSelect,
}: Props) {
  const probe = group.primary;
  const corroboration = summarizeCorroboration(probe, official, community);
  const probeStyle = STATUS_STYLES[probe.status];
  const officialStyle = official
    ? OFFICIAL_STYLES[official.status]
    : OFFICIAL_STYLES.unavailable;
  const communityStyle = community
    ? COMMUNITY_STYLES[community.status]
    : COMMUNITY_STYLES.unavailable;

  return (
    <button
      type="button"
      onClick={onSelect}
      className="mag-card w-full text-left cursor-pointer group/card"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 style={typeLg} className="text-zinc-900 dark:text-zinc-100">
          {group.name}
        </h2>
        <CorroborationBadge summary={corroboration} compact />
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-3">
        <SignalColumn title="My probe" emoji="🟢">
          <ProbeSignal probe={probe} style={probeStyle} />
        </SignalColumn>
        <SignalColumn title="Official" emoji="🏛️">
          <OfficialSignal official={official} style={officialStyle} />
        </SignalColumn>
        <SignalColumn title="Community" emoji="👥">
          <CommunitySignalPanel community={community} style={communityStyle} />
        </SignalColumn>
      </div>

      <p style={typeSm} className="mt-4 text-zinc-400 dark:text-zinc-500 group-hover/card:text-[var(--accent)] transition-colors">
        Click for attribution · fallback · history →
      </p>
    </button>
  );
}

function SignalColumn({
  title,
  emoji,
  children,
}: {
  title: string;
  emoji: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mag-card-inset !p-4 min-h-[148px] flex flex-col">
      <div style={typeSm} className="text-zinc-400 dark:text-zinc-500 flex items-center gap-1.5">
        <span aria-hidden>{emoji}</span>
        <span className="uppercase tracking-wide font-semibold">{title}</span>
      </div>
      <div className="mt-3 flex-1">{children}</div>
    </div>
  );
}

function ProbeSignal({
  probe,
  style,
}: {
  probe: ProviderHealth;
  style: (typeof STATUS_STYLES)[keyof typeof STATUS_STYLES];
}) {
  return (
    <>
      <div style={typeMdSemibold} className={`inline-flex items-center gap-2 ${style.text}`}>
        <span className={`h-2 w-2 rounded-full ${style.dot} animate-pulse`} />
        {style.label}
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span style={typeLg} className="tabular-nums text-zinc-900 dark:text-zinc-100">
          {probe.healthScore}
        </span>
        <span style={typeSm} className="text-zinc-400">/ 100</span>
        <span style={typeSm} className="ml-auto tabular-nums text-zinc-600 dark:text-zinc-400">
          {probe.latencyMs}ms
        </span>
      </div>
      {probe.model ? (
        <p className="mt-1 truncate text-zinc-400" style={monoSm}>
          {probe.model}
        </p>
      ) : null}
      <div className="mt-3 h-12">
        <LatencyChart data={probe.latencyHistory} color={style.line} height={48} />
      </div>
    </>
  );
}

function OfficialSignal({
  official,
  style,
}: {
  official?: OfficialStatusSignal;
  style: (typeof OFFICIAL_STYLES)[keyof typeof OFFICIAL_STYLES];
}) {
  if (!official) {
    return (
      <p style={typeSm} className="text-zinc-500 dark:text-zinc-400">
        Waiting for poll…
      </p>
    );
  }
  const headline =
    official.headline ??
    (official.status === "operational" ? "All systems operational" : null);

  return (
    <>
      <div style={typeMdSemibold} className={`inline-flex items-center gap-2 ${style.text}`}>
        <span className={`h-2 w-2 rounded-full ${style.dot}`} />
        {style.label}
      </div>
      {headline ? (
        <p style={typeSm} className="mt-2 text-zinc-600 dark:text-zinc-400 line-clamp-2">
          {headline}
        </p>
      ) : null}
      {official.latestPhase ? (
        <p style={typeSm} className="mt-2 text-zinc-400 dark:text-zinc-500 uppercase">
          {official.latestPhase}
        </p>
      ) : null}
    </>
  );
}

function CommunitySignalPanel({
  community,
  style,
}: {
  community?: CommunitySignal;
  style: (typeof COMMUNITY_STYLES)[keyof typeof COMMUNITY_STYLES];
}) {
  if (!community) {
    return (
      <p style={typeSm} className="text-zinc-500 dark:text-zinc-400">
        Waiting for poll…
      </p>
    );
  }

  const pct = Math.round(community.complaintRate * 100);

  return (
    <>
      <div style={typeMdSemibold} className={`inline-flex items-center gap-2 ${style.text}`}>
        <span className={`h-2 w-2 rounded-full ${style.dot}`} />
        {style.label}
      </div>
      <p style={typeSm} className="mt-2 text-zinc-600 dark:text-zinc-400">
        <span className="tabular-nums font-semibold text-zinc-800 dark:text-zinc-200">
          {pct}%
        </span>{" "}
        complaint rate
        <span className="text-zinc-400 dark:text-zinc-500">
          {" "}
          · {community.matchedPosts}/{community.postCount} posts
        </span>
      </p>
      <div className="mt-3 h-2 rounded-full bg-zinc-100 dark:bg-zinc-800 overflow-hidden">
        <div
          className={`h-full rounded-full ${style.bar}`}
          style={{ width: `${Math.min(100, pct * 2)}%` }}
        />
      </div>
    </>
  );
}
