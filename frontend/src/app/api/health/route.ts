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
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        console.error(`backend returned HTTP ${res.status}: ${body.slice(0, 500)}`);
        throw new Error(`backend HTTP ${res.status}`);
      }
      const data = await res.json();
      return NextResponse.json({ ...data, source: "live" as const });
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "unknown backend error";
      console.error("backend health fetch failed:", message);
      return NextResponse.json(
        {
          ...buildMockSnapshot(),
          source: "mock" as const,
          backendError: message,
        },
        {
          status: 200,
          headers: {
            "x-watchtower-fallback": "mock",
            "x-watchtower-error": message.slice(0, 200),
          },
        },
      );
    }
  }
  return NextResponse.json({ ...buildMockSnapshot(), source: "mock" as const });
}
