"use client";

import { useEffect } from "react";

import { WS_BASE } from "@/lib/runtime";
import { useStore } from "@/store";

export function useScanStream(unitId: string) {
  const addFinding = useStore((state) => state.addFinding);

  useEffect(() => {
    if (!unitId) {
      return;
    }
    const ws = new WebSocket(`${WS_BASE}/ws/scans/${unitId}/live`);
    ws.onmessage = (event) => {
      addFinding(JSON.parse(event.data));
    };
    return () => ws.close();
  }, [addFinding, unitId]);
}
