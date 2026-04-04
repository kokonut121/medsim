"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { CoverageMap } from "@/types";

export function useCoverageMap(facilityId: string) {
  const [coverageMap, setCoverageMap] = useState<CoverageMap | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const result = await api.getCoverage(facilityId);
      if (!cancelled) {
        setCoverageMap(result);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [facilityId]);

  return coverageMap;
}

