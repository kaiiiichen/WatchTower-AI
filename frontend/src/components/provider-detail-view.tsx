"use client";

import type { ProviderGroup } from "@/lib/provider-aggregate";
import {
  findAlertsForProvider,
  findCommunity,
  findOfficial,
  summarizeCorroboration,
} from "@/lib/provider-aggregate";
import type { CommunitySignal, HealthSnapshot, OfficialStatusSignal } from "@/lib/types";
import {
  COMMUNITY_STYLES,
  OFFICIAL_STYLES,
  STATUS_STYLES,
  accentLink,
  monoSm,
  typeLg,
  typeMd,
  typeMdSemibold,
  typeSm,
} from "@/lib/style-maps";
import AlertBanner from "./AlertBanner";
import CorroborationBadge from "./corroboration-badge";
import LatencyChart from "./LatencyChart";
import ProviderCard from "./ProviderCard";

type Props = {
  group: ProviderGroup;
  snap: HealthSnapshot;
  onBack: () => void;
};

export default function ProviderDetailView({ group, snap, onBack }: Props) {
  const official = findOfficial(group.name, snap.official);
  const community = findCommunity(group.name, snap.community);
  const alerts = findAlertsForProvider(group, snap.alerts);
  const corroboration = summarizeCorroboration(group.primary, official, community);

  return (
    <div className="max-w-[1000px] space-y-8">
      <button
        type="button"
        onClick={onBack}
        style={typeSm}
        className="text-zinc-500 hover:text-[var(--accent)] transition-colors"
      >
        ← Back to dashboard
      </button>

      <div className="flex flex-wrap items-center gap-3">
        <h2 style={typeLg} className="text-zinc-900 dark:text-zinc-100">
          {group.name}
        </h2>
        <CorroborationBadge summary={corroboration} />
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <MiniSignal
          label="My probe"
          emoji="🟢"
          status={STATUS_STYLES[group.primary.status].label}
          statusClass={STATUS_STYLES[group.primary.status].text}
          dot={STATUS_STYLES[group.primary.status].dot}
        />
        <MiniSignal
          label="Official"
          emoji="🏛️"
          status={
            official
              ? OFFICIAL_STYLES[official.status].label
              : "Unavailable"
          }
          statusClass={
            official
              ? OFFICIAL_STYLES[official.status].text
              : OFFICIAL_STYLES.unavailable.text
          }
          dot={
            official
              ? OFFICIAL_STYLES[official.status].dot
              : OFFICIAL_STYLES.unavailable.dot
          }
        />
        <MiniSignal
          label="Community"
          emoji="👥"
          status={
            community
              ? COMMUNITY_STYLES[community.status].label
              : "No signal"
          }
          statusClass={
            community
              ? COMMUNITY_STYLES[community.status].text
              : COMMUNITY_STYLES.unavailable.text
          }
          dot={
            community
              ? COMMUNITY_STYLES[community.status].dot
              : COMMUNITY_STYLES.unavailable.dot
          }
        />
      </div>

      {alerts.length ? (
        <section className="space-y-4">
          <div className="mag-label">Attribution &amp; actions</div>
          {alerts.map((a) => (
            <AlertBanner key={a.id} alert={a} />
          ))}
        </section>
      ) : (
        <p style={typeMd} className="text-zinc-500 dark:text-zinc-500">
          No active alerts for {group.name} — all signals within normal bounds.
        </p>
      )}

      <section>
        <div className="mag-label">Probe tiers</div>
        <div className="grid gap-6 sm:grid-cols-2">
          {group.tiers.map((p) => (
            <ProviderCard key={p.id} p={p} />
          ))}
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <OfficialDetail official={official} />
        <CommunityDetail community={community} />
      </section>

      <section>
        <div className="mag-label">Latency history</div>
        <div className="mag-card">
          <p style={typeSm} className="text-zinc-400 dark:text-zinc-500 mb-4">
            Primary tier ({group.primary.tier ?? "default"}) — last{" "}
            {group.primary.latencyHistory.length} probes
          </p>
          <div className="h-24">
            <LatencyChart
              data={group.primary.latencyHistory}
              color={STATUS_STYLES[group.primary.status].line}
              height={96}
            />
          </div>
        </div>
      </section>
    </div>
  );
}

function MiniSignal({
  label,
  emoji,
  status,
  statusClass,
  dot,
}: {
  label: string;
  emoji: string;
  status: string;
  statusClass: string;
  dot: string;
}) {
  return (
    <div className="mag-card-inset !p-4">
      <div style={typeSm} className="text-zinc-400 dark:text-zinc-500">
        {emoji} {label}
      </div>
      <div style={typeMdSemibold} className={`mt-2 inline-flex items-center gap-2 ${statusClass}`}>
        <span className={`h-2 w-2 rounded-full ${dot}`} />
        {status}
      </div>
    </div>
  );
}

function OfficialDetail({ official }: { official?: OfficialStatusSignal }) {
  if (!official) {
    return (
      <div className="mag-card">
        <div className="mag-label">Official status</div>
        <p style={typeMd} className="text-zinc-500">No data yet.</p>
      </div>
    );
  }
  const s = OFFICIAL_STYLES[official.status];
  return (
    <div className="mag-card">
      <div className="mag-label">Official status</div>
      <div className="flex items-center justify-between gap-2">
        <span style={typeMdSemibold} className={s.text}>
          <span className={`inline-block h-2 w-2 rounded-full mr-2 ${s.dot}`} />
          {s.label}
        </span>
      </div>
      {official.headline ? (
        <p style={typeMd} className="mt-3 text-zinc-700 dark:text-zinc-300">
          {official.headline}
        </p>
      ) : null}
      {official.latestUpdate ? (
        <p style={typeSm} className="mt-2 text-zinc-500">{official.latestUpdate}</p>
      ) : null}
      {official.componentSummary ? (
        <p style={monoSm} className="mt-2 text-zinc-400">{official.componentSummary}</p>
      ) : null}
      {official.pageUrl ? (
        <a
          href={official.pageUrl}
          target="_blank"
          rel="noopener noreferrer"
          style={typeMd}
          className={`mt-4 inline-block ${accentLink}`}
        >
          Open status page →
        </a>
      ) : null}
    </div>
  );
}

function CommunityDetail({ community }: { community?: CommunitySignal }) {
  if (!community) {
    return (
      <div className="mag-card">
        <div className="mag-label">Community</div>
        <p style={typeMd} className="text-zinc-500">No data yet.</p>
      </div>
    );
  }
  const s = COMMUNITY_STYLES[community.status];
  const pct = Math.round(community.complaintRate * 100);
  return (
    <div className="mag-card">
      <div className="mag-label">Community · Hacker News</div>
      <div style={typeMdSemibold} className={s.text}>
        <span className={`inline-block h-2 w-2 rounded-full mr-2 ${s.dot}`} />
        {s.label} · {pct}% complaint rate
      </div>
      <p style={typeMd} className="mt-3 text-zinc-600 dark:text-zinc-400">
        {community.matchedPosts} matched of {community.postCount} posts in last{" "}
        {community.lookbackHours ?? 24}h
        {community.baseline > 0 ? (
          <>
            {" "}
            · baseline{" "}
            <span className="tabular-nums">
              {Math.round(community.baseline * 100)}%
            </span>
          </>
        ) : null}
      </p>
      {community.searchQuery ? (
        <p style={typeSm} className="mt-2 text-zinc-400">
          Query: &ldquo;{community.searchQuery}&rdquo;
        </p>
      ) : null}
    </div>
  );
}
