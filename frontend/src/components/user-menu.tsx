"use client";

import { useEffect, useRef, useState } from "react";
import DashboardSettings from "@/components/dashboard-settings";
import { typeSm, typeSmSemibold } from "@/lib/style-maps";

type Props = {
  pollSeconds: number;
  source?: "live";
  compact?: boolean;
};

export default function UserMenu({ pollSeconds, source, compact }: Props) {
  const [open, setOpen] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        setShowSettings(false);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className={`relative ${compact ? "pt-2" : "border-t border-zinc-100 dark:border-zinc-800/80 px-3 py-3"}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={
          compact
            ? "mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-[var(--accent)] text-white text-sm font-semibold hover:opacity-90 transition-opacity"
            : "flex w-full items-center gap-3 rounded-md px-2 py-2 hover:bg-zinc-50 dark:hover:bg-zinc-900/50 transition-colors"
        }
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="Account menu"
        title="Settings"
      >
        W
        {!compact ? (
          <span className="min-w-0 text-left">
            <span style={typeSmSemibold} className="block text-zinc-800 dark:text-zinc-200 truncate">
              Local
            </span>
            <span style={typeSm} className="block text-zinc-400 dark:text-zinc-500 truncate">
              {source === "live" ? "Live probes" : "Backend offline"}
            </span>
          </span>
        ) : null}
      </button>

      {open ? (
        <div
          role="menu"
          className={`absolute bottom-full mb-1 rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-[#252019] shadow-[3px_3px_0_0_var(--color-border-tertiary)] py-1 z-50 ${
            compact ? "left-full ml-2 bottom-0 mb-0 w-36" : "left-2 right-2"
          }`}
        >
          <button
            type="button"
            role="menuitem"
            style={typeSm}
            className="w-full px-3 py-2 text-left text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-900/50"
            onClick={() => {
              setShowSettings(true);
              setOpen(false);
            }}
          >
            Settings
          </button>
        </div>
      ) : null}

      {showSettings ? (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/30">
          <div
            className="w-full max-w-md max-h-[85vh] overflow-y-auto rounded-md border border-zinc-200 dark:border-zinc-700 bg-[var(--background)] shadow-[5px_5px_0_0_var(--color-border-tertiary)] p-6"
            role="dialog"
            aria-labelledby="settings-title"
          >
            <div className="flex items-center justify-between gap-4 mb-4">
              <h2 id="settings-title" style={typeSmSemibold} className="text-zinc-900 dark:text-zinc-100">
                Settings
              </h2>
              <button
                type="button"
                onClick={() => setShowSettings(false)}
                style={typeSm}
                className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
              >
                Close
              </button>
            </div>
            <DashboardSettings pollSeconds={pollSeconds} source={source} />
          </div>
        </div>
      ) : null}
    </div>
  );
}
