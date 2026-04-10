import { WorldViewer } from "@/components/viewer/WorldViewer";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

async function getSplatUrl(): Promise<string> {
  const fallback = `${API}/api/models/unit_1/splat/stream`;
  try {
    const res = await fetch(`${API}/api/models/unit_1/splat`, { cache: "no-store" });
    if (!res.ok) return fallback;
    const data = (await res.json()) as { stream_url?: string };
    // stream_url is a relative path — prefix with API base
    return data.stream_url ? `${API}${data.stream_url}` : fallback;
  } catch {
    return fallback;
  }
}

export default async function LandingPage() {
  const splatUrl = await getSplatUrl();
  return (
    <main className="demo-root">
      <WorldViewer initialSplatUrl={splatUrl} />
    </main>
  );
}
