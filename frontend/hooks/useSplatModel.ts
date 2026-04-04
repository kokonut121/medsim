"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

export function useSplatModel(unitId: string) {
  const [signedUrl, setSignedUrl] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await api.getSplat(unitId);
        if (!cancelled) {
          setSignedUrl(result.signed_url);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [unitId]);

  return { signedUrl, loading };
}

