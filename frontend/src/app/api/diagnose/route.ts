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
    const res = await fetch(`${backend}/diagnose`, { cache: "no-store" });
    if (!res.ok) {
      return backendOfflineResponse(`Backend returned HTTP ${res.status}.`);
    }
    return NextResponse.json(await res.json());
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "unknown backend error";
    console.error("backend diagnose fetch failed:", message);
    return backendOfflineResponse("Backend offline.");
  }
}
