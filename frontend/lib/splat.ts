import { buildApiUrl } from "@/lib/runtime";

export interface SplatAssetResponse {
  signed_url: string;
  stream_url?: string;
}

export function getFallbackSplatUrl(unitId: string): string {
  return buildApiUrl(`/api/models/${unitId}/splat/stream`);
}

export function resolveSplatAssetUrl(result: SplatAssetResponse): string {
  return result.stream_url ? buildApiUrl(result.stream_url) : result.signed_url;
}

export function isSplatAssetUrl(url: string): boolean {
  return (
    url.endsWith(".spz") ||
    url.endsWith(".bin") ||
    url.includes("/splat/stream") ||
    url.includes("/splat/")
  );
}
