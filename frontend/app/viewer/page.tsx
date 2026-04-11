import { WorldViewer } from "@/components/viewer/WorldViewer";
import { buildApiUrl } from "@/lib/runtime";
import { resolveSplatAssetUrl } from "@/lib/splat";

async function getSplatUrl(): Promise<string> {
  try {
    const res = await fetch(buildApiUrl("/api/models/unit_1/splat"), { cache: "no-store" });
    if (!res.ok) return "";
    return resolveSplatAssetUrl(
      (await res.json()) as { signed_url: string; stream_url?: string },
    );
  } catch {
    return "";
  }
}

export default async function ViewerPage() {
  const splatUrl = await getSplatUrl();
  return (
    <main className="demo-root">
      <WorldViewer initialSplatUrl={splatUrl} />
    </main>
  );
}
