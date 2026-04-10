"use client";

import { useEffect, useRef } from "react";

import { useStore } from "@/store";

export function ReasoningStream() {
  const buffer = useStore((state) => state.reasoningBuffer);
  const status = useStore((state) => state.simulationStatus);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [buffer]);

  return (
    <div className="panel" style={{ display: "grid", gap: 12 }}>
      <div>
        <div className="eyebrow">Supervisor</div>
        <h2 style={{ margin: "8px 0 4px" }}>Reasoning stream</h2>
        <p className="muted" style={{ margin: 0, fontSize: 12 }}>
          gpt-4o is analysing the swarm aggregate and producing a tactical best-plan report.
        </p>
      </div>
      <div
        ref={scrollRef}
        style={{
          fontFamily: "ui-monospace, 'SFMono-Regular', monospace",
          fontSize: 12,
          padding: 12,
          minHeight: 140,
          maxHeight: 260,
          overflowY: "auto",
          background: "rgba(0,0,0,0.25)",
          borderRadius: 6,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word"
        }}
      >
        {buffer ||
          (status === "reasoning"
            ? "Reasoning…"
            : status === "complete"
              ? "Reasoning complete."
              : "Idle — launch a scenario to see the supervisor reason in real time.")}
      </div>
    </div>
  );
}
