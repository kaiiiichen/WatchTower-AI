import { NextResponse } from "next/server";

export function resolveBackendUrl(): string | null {
  const url = process.env.BACKEND_URL?.trim();
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
    return url;
  } catch {
    return null;
  }
}

export function backendOfflineResponse(message = "Backend offline", status = 503) {
  return NextResponse.json({ error: message }, { status });
}
