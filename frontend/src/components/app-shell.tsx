"use client";

import { useEffect, useState, type ReactNode } from "react";
import WatchTowerLogo from "@/components/watchtower-logo";
import UserMenu from "@/components/user-menu";
import { PAGE_NAV, type PageSection, scrollToSection } from "@/lib/dashboard-nav";
import { SEMANTIC_COLORS, monoSm } from "@/lib/style-maps";

type Props = {
  alertCount?: number;
  pollSeconds: number;
  dataSource?: "live";
  children: ReactNode;
};

function NavIcon({ id, active }: { id: PageSection; active: boolean }) {
  const stroke = active ? "var(--accent)" : "currentColor";
  const common = {
    width: 20,
    height: 20,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke,
    strokeWidth: 1.75,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };

  switch (id) {
    case "dashboard":
      return (
        <svg {...common}>
          <rect x="3" y="3" width="7" height="9" rx="1" />
          <rect x="14" y="3" width="7" height="5" rx="1" />
          <rect x="14" y="12" width="7" height="9" rx="1" />
          <rect x="3" y="16" width="7" height="5" rx="1" />
        </svg>
      );
    case "diagnostics":
      return (
        <svg {...common}>
          <path d="M9 11l3 3L22 4" />
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
        </svg>
      );
    case "about":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="10" />
          <path d="M12 16v-4M12 8h.01" />
        </svg>
      );
  }
}

export default function AppShell({
  alertCount = 0,
  pollSeconds,
  dataSource,
  children,
}: Props) {
  const [active, setActive] = useState<PageSection>("dashboard");

  useEffect(() => {
    const anchors = PAGE_NAV.map((n) => document.getElementById(n.anchor)).filter(Boolean);
    if (!anchors.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        const top = visible[0]?.target.id;
        if (!top) return;
        const match = PAGE_NAV.find((n) => n.anchor === top);
        if (match) setActive(match.id);
      },
      { rootMargin: "-20% 0px -60% 0px", threshold: [0, 0.15, 0.4] }
    );

    for (const el of anchors) observer.observe(el!);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--background)]">
      <aside className="flex w-14 shrink-0 flex-col items-center border-r border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#1a1612] py-4">
        <a
          href="#section-dashboard"
          onClick={(e) => {
            e.preventDefault();
            scrollToSection("section-dashboard");
          }}
          className="mb-6 text-[var(--accent)]"
          aria-label="WatchTower home"
        >
          <WatchTowerLogo size={28} showOrbit={false} showSignal={false} />
        </a>

        <nav className="flex flex-1 flex-col items-center gap-1">
          {PAGE_NAV.map((item) => {
            const isActive = active === item.id;
            return (
              <button
                key={item.id}
                type="button"
                title={item.label}
                aria-label={item.label}
                aria-current={isActive ? "true" : undefined}
                onClick={() => scrollToSection(item.anchor)}
                className={[
                  "relative flex h-10 w-10 items-center justify-center rounded-md transition-colors",
                  isActive
                    ? "bg-[#FFFAF6] dark:bg-[#2a221c] text-[var(--accent)]"
                    : "text-zinc-400 dark:text-zinc-500 hover:bg-zinc-50 dark:hover:bg-zinc-900/50 hover:text-zinc-700 dark:hover:text-zinc-300",
                ].join(" ")}
              >
                {isActive ? (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-[var(--accent)] rounded-r" />
                ) : null}
                <NavIcon id={item.id} active={isActive} />
                {item.id === "dashboard" && alertCount > 0 ? (
                  <span
                    style={monoSm}
                    className={`absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full px-0.5 tabular-nums text-[10px] ${SEMANTIC_COLORS.rose.chip}`}
                  >
                    {alertCount}
                  </span>
                ) : null}
              </button>
            );
          })}
        </nav>

        <div className="mt-auto w-full px-1">
          <UserMenu pollSeconds={pollSeconds} source={dataSource} compact />
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
