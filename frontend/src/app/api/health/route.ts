import { NextResponse } from "next/server";
import { buildMockSnapshot } from "@/lib/mock-data";

// Health endpoint. If BACKEND_URL is set, proxy the real FastAPI probe engine;
// otherwise serve mock data so the dashboard works standalone.
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
  if (backend) {
    if (!isAllowedBackendUrl(backend)) {
      return NextResponse.json({ ...buildMockSnapshot(), source: "mock" as const }, {
        status: 502,
        headers: { "x-watchtower-fallback": "invalid-backend-url" },
      });
    }
    try {
      const res = await fetch(`${backend}/health`, { cache: "no-store" });
      if (!res.ok) throw new Error(`backend HTTP ${res.status}`);
      const data = await res.json();
      return NextResponse.json({ ...data, source: "live" as const });
    } catch {
      // Surface the failure but keep the dashboard alive on mock data.
      return NextResponse.json({ ...buildMockSnapshot(), source: "mock" as const }, {
        headers: { "x-watchtower-fallback": "mock" },
      });
    }
  }
  return NextResponse.json({ ...buildMockSnapshot(), source: "mock" as const });
}
