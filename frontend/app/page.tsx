import { WorldViewer } from "@/components/viewer/WorldViewer";
import { buildApiUrl } from "@/lib/runtime";
import { getFallbackSplatUrl, resolveSplatAssetUrl } from "@/lib/splat";

async function getSplatUrl(): Promise<string> {
  const fallback = getFallbackSplatUrl("unit_1");
  try {
    const res = await fetch(buildApiUrl("/api/models/unit_1/splat"), { cache: "no-store" });
    if (!res.ok) return fallback;
    return resolveSplatAssetUrl(
      (await res.json()) as { signed_url: string; stream_url?: string },
    );
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
