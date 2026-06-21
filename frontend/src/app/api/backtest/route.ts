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
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(`${backend}/backtest`, {
      cache: "no-store",
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) {
      return backendOfflineResponse(`Backend returned HTTP ${res.status}.`);
    }
    return NextResponse.json(await res.json());
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "unknown backend error";
    console.error("backend backtest fetch failed:", message);
    return backendOfflineResponse("Backend offline.");
  }
}
