import { WorldViewer } from "@/components/viewer/WorldViewer";
import { buildApiUrl } from "@/lib/runtime";

async function getViewerUrl(): Promise<string> {
  try {
    const res = await fetch(buildApiUrl("/api/models/unit_1/status"), { cache: "no-store" });
    if (!res.ok) return "";
    const data = await res.json() as { world_marble_url?: string };
    return data.world_marble_url ?? "";
  } catch {
    return "";
  }
}

export default async function ViewerPage() {
  const splatUrl = await getViewerUrl();
  return (
    <main className="demo-root">
      <WorldViewer initialSplatUrl={splatUrl} />
    </main>
  );
}
