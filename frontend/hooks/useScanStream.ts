"use client";

import { useEffect } from "react";

import { WS_BASE } from "@/lib/runtime";
import { useStore } from "@/store";
import type { Finding } from "@/types";

export function useScanStream(unitId: string) {
  const addFinding = useStore((state) => state.addFinding);

  useEffect(() => {
    if (!unitId) {
      return;
    }
    const ws = new WebSocket(`${WS_BASE}/ws/scans/${unitId}/live`);
    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data) as { type?: string } & Partial<Finding>;
      if (payload.type === "finding") {
        addFinding(payload as Finding);
      }
    };
    return () => ws.close();
  }, [addFinding, unitId]);
}
