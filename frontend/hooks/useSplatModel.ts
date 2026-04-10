"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { ModelStatusResponse } from "@/types";

export function useSplatModel(unitId: string) {
  const [signedUrl, setSignedUrl] = useState<string>("");
  const [status, setStatus] = useState<ModelStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let intervalId: number | null = null;

    async function refresh() {
      try {
        const currentStatus = await api.getModelStatus(unitId);
        if (!cancelled) {
          setStatus(currentStatus);
        }
        if (currentStatus.status === "ready") {
          const result = await api.getSplat(unitId);
          if (!cancelled) {
            // Prefer the CORS-safe proxy stream URL over the direct R2 signed URL
            const base = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
            const url = result.stream_url
              ? `${base}${result.stream_url}`
              : result.signed_url;
            setSignedUrl(url);
            setError(null);
          }
        } else if (!cancelled) {
          setSignedUrl("");
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load model state");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void refresh();
    intervalId = window.setInterval(() => {
      void refresh();
    }, 3000);

    return () => {
      cancelled = true;
      if (intervalId) {
        window.clearInterval(intervalId);
      }
    };
  }, [unitId]);

  return { signedUrl, status, loading, error };
}
