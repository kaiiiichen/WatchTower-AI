"use client";

import { useState } from "react";
import type {
  CommunitySignal,
  DowndetectorSourceEntry,
  HackerNewsSourceEntry,
} from "@/lib/types";
import {
  COMMUNITY_STYLES,
  accentLink,
  monoSm,
  typeLg,
  typeMd,
  typeMdSemibold,
  typeSm,
  typeSmSemibold,
  typeStat,
} from "@/lib/style-maps";
import MagChip from "./mag-chip";

const HACKER_NEWS_URL = "https://news.ycombinator.com/";
const HN_ALGOLIA_API_URL = "https://hn.algolia.com/api";
const DOWNDETECTOR_URL = "https://downdetector.com/";
const BROWSERBASE_URL = "https://www.browserbase.com/";

export default function CommunitySignals({ signals }: { signals: CommunitySignal[] }) {
  const [whyOpen, setWhyOpen] = useState(false);
  if (!signals.length) return null;

  const lookbackHours = signals[0]?.lookbackHours ?? 24;

  return (
    <section aria-label="Community signal">
      <div className="mag-label">Community signal</div>
      <p style={typeMd} className="-mt-2 mb-6 text-zinc-400 dark:text-zinc-600 max-w-2xl">
        Community corroboration from{" "}
        <a
          href={HACKER_NEWS_URL}
          target="_blank"
          rel="noopener noreferrer"
          className={accentLink}
        >
          Hacker News
        </a>{" "}
        and Downdetector — may flag a provider before your probe does.
      </p>

      <div className="space-y-8">
        <div>
          <p style={typeSmSemibold} className="mb-3 text-zinc-500 dark:text-zinc-400">
            Hacker News · last {lookbackHours}h
          </p>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {signals.map((sig) => (
              <HnSignalCard key={sig.providerId} sig={sig} lookbackHours={lookbackHours} />
            ))}
          </div>
        </div>

        <div>
          <p style={typeSmSemibold} className="mb-3 text-zinc-500 dark:text-zinc-400">
            Downdetector
          </p>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {signals.map((sig) => (
              <DowndetectorCard key={`dd-${sig.providerId}`} sig={sig} />
            ))}
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2">
        <MagChip
          as="button"
          size="sm"
          arrow={whyOpen ? "left" : "right"}
          onClick={() => setWhyOpen((v) => !v)}
          aria-expanded={whyOpen}
        >
          {whyOpen ? "Hide" : "How we source community data"}
        </MagChip>
        <p style={typeSm} className="text-zinc-400 dark:text-zinc-500">
          HN via{" "}
          <a
            href={HN_ALGOLIA_API_URL}
            target="_blank"
            rel="noopener noreferrer"
            className={accentLink}
          >
            Algolia Search API
          </a>
          {" · "}
          Downdetector via{" "}
          <a
            href={BROWSERBASE_URL}
            target="_blank"
            rel="noopener noreferrer"
            className={accentLink}
          >
            Browserbase
          </a>
        </p>
      </div>

      {whyOpen ? (
        <div className="mt-3 mag-card-inset space-y-4">
          <div>
            <p style={typeMdSemibold} className="text-zinc-800 dark:text-zinc-200">
              Hacker News — why not Reddit?
            </p>
            <p style={typeMd} className="mt-2 text-zinc-600 dark:text-zinc-400">
              Reddit now requires manual approval before you can create an OAuth app
              and read public subreddit data. Devvit only runs inside Reddit — fine for
              mod tools, not for an external outage monitor like WatchTower.
            </p>
            <p style={typeMd} className="mt-2 text-zinc-600 dark:text-zinc-400">
              <a
                href={HACKER_NEWS_URL}
                target="_blank"
                rel="noopener noreferrer"
                className={accentLink}
              >
                Hacker News
              </a>{" "}
              exposes a public{" "}
              <a
                href={HN_ALGOLIA_API_URL}
                target="_blank"
                rel="noopener noreferrer"
                className={accentLink}
              >
                Algolia search API
              </a>{" "}
              — no key, no approval queue. We scan the last {lookbackHours} hours of
              stories per provider for outage keywords (&ldquo;down&rdquo;,
              &ldquo;outage&rdquo;, &ldquo;not working&rdquo;, …).
            </p>
          </div>

          <div>
            <p style={typeMdSemibold} className="text-zinc-800 dark:text-zinc-200">
              Downdetector — honest disclosure
            </p>
            <p style={typeMd} className="mt-2 text-zinc-600 dark:text-zinc-400">
              <a
                href={DOWNDETECTOR_URL}
                target="_blank"
                rel="noopener noreferrer"
                className={accentLink}
              >
                Downdetector
              </a>{" "}
              is, in a sense, a competing product — they aggregate crowd reports the
              same way we try to. We don&apos;t have a partnership or API access. Instead,
              we use{" "}
              <a
                href={BROWSERBASE_URL}
                target="_blank"
                rel="noopener noreferrer"
                className={accentLink}
              >
                Browserbase
              </a>{" "}
              to open a real browser session and read the live public report pages each
              poll cycle, then summarize what users are saying.
            </p>
            <p style={typeMd} className="mt-2 text-zinc-600 dark:text-zinc-400">
              Thank you to Downdetector and their community for publishing that signal —
              we&apos;re borrowing their public data, not replacing them. WatchTower is a
              personal indie project for developers watching their own API keys, not a
              commercial outage service.
            </p>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function findDowndetector(sig: CommunitySignal): DowndetectorSourceEntry | undefined {
  return sig.sources?.find(
    (s): s is DowndetectorSourceEntry => s.source === "Downdetector"
  );
}

function hnSignalView(
  community: CommunitySignal
): {
  status: CommunitySignal["status"];
  complaintRate: number;
  postCount: number;
  matchedPosts: number;
  baseline: number;
  searchQuery?: string | null;
} | null {
  const raw = community.sources?.find(
    (s): s is HackerNewsSourceEntry => s.source === "hackernews"
  );
  if (raw) {
    if (raw.status === "unavailable") return null;
    const status =
      raw.spike === true || raw.status === "spike"
        ? ("spike" as const)
        : raw.status;
    return {
      status,
      complaintRate: raw.complaintRate ?? 0,
      postCount: raw.postCount ?? 0,
      matchedPosts: raw.matchedPosts ?? 0,
      baseline: raw.baseline ?? community.baseline,
      searchQuery: raw.searchQuery ?? community.searchQuery,
    };
  }
  if (community.status === "unavailable") return null;
  if (community.source && !community.source.toLowerCase().includes("hackernews")) {
    return null;
  }
  return {
    status: community.status,
    complaintRate: community.complaintRate,
    postCount: community.postCount,
    matchedPosts: community.matchedPosts,
    baseline: community.baseline,
    searchQuery: community.searchQuery,
  };
}

function HnSignalCard({
  sig,
  lookbackHours,
}: {
  sig: CommunitySignal;
  lookbackHours: number;
}) {
  const hn = hnSignalView(sig);
  const unavailable = !hn || hn.status === "unavailable";
  const s = COMMUNITY_STYLES[unavailable ? "unavailable" : hn!.status];
  const pct = hn ? Math.min(100, Math.round(hn.complaintRate * 100)) : 0;

  return (
    <div className="mag-card">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span style={typeLg} className="text-zinc-900 dark:text-zinc-100">
            {sig.providerId}
          </span>
          {hn?.searchQuery ? (
            <span className="truncate text-zinc-400 dark:text-zinc-500" style={monoSm}>
              HN · {hn.searchQuery}
            </span>
          ) : null}
        </div>
        <span style={typeMdSemibold} className={`inline-flex shrink-0 items-center gap-1.5 ${s.text}`}>
          <span
            className={`h-2 w-2 rounded-full ${s.dot} ${
              hn?.status === "spike" ? "animate-pulse" : ""
            }`}
            aria-hidden
          />
          {s.label}
        </span>
      </div>

      {unavailable ? (
        <p style={typeMd} className="mt-3 text-zinc-500 dark:text-zinc-400">
          Signal unavailable — main probes unaffected.
        </p>
      ) : (
        <>
          <div className="mt-4 flex items-baseline gap-2">
            <span style={typeStat} className="tabular-nums text-zinc-900 dark:text-zinc-100">
              {pct}%
            </span>
            <span style={typeSm} className="text-zinc-400 dark:text-zinc-500">
              complaint rate · last {lookbackHours}h
            </span>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
            <div className={`h-full ${s.bar}`} style={{ width: `${pct}%` }} />
          </div>
          <p style={typeSm} className="mt-2 tabular-nums text-zinc-400 dark:text-zinc-500">
            {hn!.matchedPosts}/{hn!.postCount} stories · baseline{" "}
            {Math.round(hn!.baseline * 100)}%
          </p>
        </>
      )}
    </div>
  );
}

function DowndetectorCard({ sig }: { sig: CommunitySignal }) {
  const dd = findDowndetector(sig);

  return (
    <div className="mag-card">
      <span style={typeLg} className="text-zinc-900 dark:text-zinc-100">
        {sig.providerId}
      </span>

      {!dd ? (
        <p style={typeMd} className="mt-3 text-zinc-500 dark:text-zinc-400">
          No Downdetector data this cycle.
        </p>
      ) : (
        <div className="mt-3 space-y-3">
          {dd.headline ? (
            <p style={typeMd} className="text-zinc-700 dark:text-zinc-300">
              {dd.headline}
            </p>
          ) : null}

          <div className="mag-card-inset">
            <p style={typeSm} className="text-zinc-400 dark:text-zinc-500 uppercase tracking-wide">
              Insight
            </p>
            <p style={typeMd} className="mt-1 text-zinc-800 dark:text-zinc-200">
              {dd.summary?.trim() || "No summary this cycle."}
            </p>
          </div>

          {typeof dd.count === "number" ? (
            <p style={typeSm} className="tabular-nums text-zinc-400 dark:text-zinc-500">
              {dd.count} report{dd.count === 1 ? "" : "s"} (&lt;24h)
            </p>
          ) : null}

          {dd.comments?.length ? (
            <ul className="space-y-2">
              {dd.comments.map((c, i) => (
                <li key={i} style={typeSm} className="text-zinc-600 dark:text-zinc-400">
                  <span className="text-zinc-400 dark:text-zinc-500">[{c.age}] </span>
                  {c.text}
                </li>
              ))}
            </ul>
          ) : null}

          {dd.url ? (
            <a
              href={dd.url}
              target="_blank"
              rel="noopener noreferrer"
              style={typeMd}
              className={`inline-block ${accentLink}`}
            >
              View on Downdetector
            </a>
          ) : null}
        </div>
      )}
    </div>
  );
}
