"use client";

import { useTheme } from "@/components/theme-provider";
import { typeMd, typeSm, typeSmSemibold } from "@/lib/style-maps";

type Props = {
  pollSeconds: number;
  source?: "live";
};

export default function DashboardSettings({ pollSeconds, source }: Props) {
  const { theme, setTheme } = useTheme();

  return (
    <div className="max-w-lg space-y-6">
      <section className="mag-card">
        <h2 style={typeSmSemibold} className="text-zinc-700 dark:text-zinc-300">
          Appearance
        </h2>
        <p style={typeSm} className="mt-2 text-zinc-500 dark:text-zinc-500">
          Choose light or dark mode.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {(["light", "dark"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTheme(t)}
              className={[
                "mag-chip capitalize",
                theme === t
                  ? "!border-[var(--accent)] !text-[var(--accent)] !bg-[#FFFAF6] dark:!bg-[#2a221c]"
                  : "",
              ].join(" ")}
            >
              {t}
            </button>
          ))}
        </div>
      </section>

      <section className="mag-card">
        <h2 style={typeSmSemibold} className="text-zinc-700 dark:text-zinc-300">
          Polling
        </h2>
        <p style={typeMd} className="mt-3 text-zinc-600 dark:text-zinc-400">
          Health data refreshes every{" "}
          <span className="tabular-nums font-semibold text-zinc-800 dark:text-zinc-200">
            {pollSeconds}s
          </span>
          {source === "live" ? " from your configured API keys." : " when the backend is connected."}
        </p>
      </section>
    </div>
  );
}
