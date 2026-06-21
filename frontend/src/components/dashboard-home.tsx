"use client";

import type { HealthSnapshot } from "@/lib/types";
import {
  findCommunity,
  findOfficial,
  groupProvidersByName,
  type ProviderName,
} from "@/lib/provider-aggregate";
import ProviderUnifiedCard from "./provider-unified-card";

type Props = {
  snap: HealthSnapshot | null;
  onSelectProvider: (name: ProviderName) => void;
};

export default function DashboardHome({ snap, onSelectProvider }: Props) {
  const groups = snap ? groupProvidersByName(snap.providers) : [];

  return (
    <div className="max-w-[1100px] space-y-6">
      {!snap ? (
        <div className="space-y-6">
          {(["Claude", "GPT", "Gemini"] as const).map((name) => (
            <div
              key={name}
              className="mag-card h-52 animate-pulse bg-zinc-100 dark:bg-zinc-800/50"
            />
          ))}
        </div>
      ) : (
        groups.map((group) => (
          <ProviderUnifiedCard
            key={group.name}
            group={group}
            official={findOfficial(group.name, snap.official)}
            community={findCommunity(group.name, snap.community)}
            onSelect={() => onSelectProvider(group.name)}
          />
        ))
      )}
    </div>
  );
}
