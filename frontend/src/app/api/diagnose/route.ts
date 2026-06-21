import { NextResponse } from "next/server";
import { buildMockDiagnosis } from "@/lib/mock-data";

// Local-diagnostics endpoint. If BACKEND_URL is set, proxy the FastAPI
// /diagnose; otherwise serve a mock so the dashboard works standalone.
export const dynamic = "force-dynamic";

function isAllowedBackendUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export async function GET() {
  const backend = process.env.BACKEND_URL;
  if (backend && isAllowedBackendUrl(backend)) {
    try {
      const res = await fetch(`${backend}/diagnose`, { cache: "no-store" });
      if (!res.ok) throw new Error(`backend HTTP ${res.status}`);
      return NextResponse.json(await res.json());
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "unknown backend error";
      console.error("backend diagnose fetch failed:", message);
      // Graceful degradation: surface an indeterminate verdict, never crash.
      return NextResponse.json(
        {
          checks: [],
          localHealthy: null,
          verdictKind: "indeterminate" as const,
          verdict: `Couldn't run diagnostics — backend unreachable (${message}).`,
          checkedAt: new Date().toISOString(),
        },
        { status: 200, headers: { "x-watchtower-fallback": "diagnose-error" } },
      );
    }
  }
  return NextResponse.json(buildMockDiagnosis());
}
