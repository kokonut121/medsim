import { WorldViewer } from "@/components/viewer/WorldViewer";
import { buildApiUrl } from "@/lib/runtime";
import { resolveSplatAssetUrl } from "@/lib/splat";

async function getSplatUrl(): Promise<string> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(buildApiUrl("/api/models/unit_1/splat"), { cache: "no-store", signal: controller.signal });
    clearTimeout(timeout);
    if (!res.ok) return "";
    return resolveSplatAssetUrl(
      (await res.json()) as { signed_url: string; stream_url?: string },
    );
  } catch {
    return "";
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
