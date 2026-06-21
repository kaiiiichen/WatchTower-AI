import { NextResponse } from "next/server";
import { buildMockBacktest } from "@/lib/mock-data";

// Detection lead-time backtest. Proxies the FastAPI /backtest (real VU-dataset
// metrics) when BACKEND_URL is set; otherwise serves the same precomputed
// numbers as a mock so the dashboard works standalone.
export const dynamic = "force-dynamic";

function isAllowedBackendUrl(url: string): boolean {
  try {
    const p = new URL(url);
    return p.protocol === "http:" || p.protocol === "https:";
  } catch {
    return false;
  }
}

export async function GET() {
  const backend = process.env.BACKEND_URL;
  if (backend && isAllowedBackendUrl(backend)) {
    try {
      const res = await fetch(`${backend}/backtest`, { cache: "no-store" });
      if (!res.ok) throw new Error(`backend HTTP ${res.status}`);
      return NextResponse.json(await res.json());
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "unknown backend error";
      console.error("backend backtest fetch failed:", message);
      // Fall back to the precomputed (identical) numbers rather than failing.
      return NextResponse.json(buildMockBacktest(), {
        headers: { "x-watchtower-fallback": "backtest-mock" },
      });
    }
  }
  return NextResponse.json(buildMockBacktest());
}
