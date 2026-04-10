"use client";

import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { getFallbackSplatUrl, resolveSplatAssetUrl } from "@/lib/splat";
import type { ModelStatusResponse } from "@/types";

export function useSplatModel(unitId: string) {
  const [signedUrl, setSignedUrl] = useState<string>("");
  const [status, setStatus] = useState<ModelStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const signedUrlRef = useRef("");

  useEffect(() => {
    let cancelled = false;
    let timeoutId: number | undefined;

    const refresh = async () => {
      try {
        const currentStatus = await api.getModelStatus(unitId);
        if (!cancelled) {
          setStatus(currentStatus);
        }

        if (currentStatus.status === "ready" && !signedUrlRef.current) {
          const result = await api.getSplat(unitId);
          if (!cancelled) {
            const url = resolveSplatAssetUrl(result);
            signedUrlRef.current = url;
            setSignedUrl(url);
            setError(null);
          }
        } else if (!cancelled) {
          if (currentStatus.status !== "ready") {
            signedUrlRef.current = "";
            setSignedUrl("");
          }

          if (currentStatus.status !== "failed") {
            timeoutId = window.setTimeout(() => {
              void refresh();
            }, 3000);
          }
        }
      } catch (loadError) {
        if (!cancelled) {
          signedUrlRef.current = "";
          setError(loadError instanceof Error ? loadError.message : "Unable to load model state");
          setSignedUrl(getFallbackSplatUrl(unitId));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    setLoading(true);
    void refresh();

    return () => {
      cancelled = true;
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [unitId]);

  return { signedUrl, status, loading, error };
}
