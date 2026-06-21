import { NextResponse } from "next/server";
import { backendOfflineResponse, resolveBackendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  const backend = resolveBackendUrl();
  if (!backend) {
    return backendOfflineResponse(
      "Backend offline — set BACKEND_URL (e.g. http://localhost:8000).",
    );
  }

  try {
    const res = await fetch(`${backend}/health`, { cache: "no-store" });
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      console.error(`backend returned HTTP ${res.status}: ${body.slice(0, 500)}`);
      return backendOfflineResponse(`Backend returned HTTP ${res.status}.`);
    }
    const data = await res.json();
    return NextResponse.json({ ...data, source: "live" as const });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "unknown backend error";
    console.error("backend health fetch failed:", message);
    return backendOfflineResponse("Backend offline.");
  }
}
