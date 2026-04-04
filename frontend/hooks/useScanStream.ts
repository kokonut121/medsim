"use client";

import { useEffect } from "react";

import { useStore } from "@/store";

export function useScanStream(unitId: string) {
  const addFinding = useStore((state) => state.addFinding);

  useEffect(() => {
    if (!unitId) {
      return;
    }
    const wsBase = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
    const ws = new WebSocket(`${wsBase}/ws/scans/${unitId}/live`);
    ws.onmessage = (event) => {
      addFinding(JSON.parse(event.data));
    };
    return () => ws.close();
  }, [addFinding, unitId]);
}

