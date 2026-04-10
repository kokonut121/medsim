"use client";

import { memo } from "react";

function CameraControllerComponent({ selectedLabel }: { selectedLabel: string | null }) {
  return (
    <div className="pill">
      {selectedLabel ? `Camera fly-to: ${selectedLabel}` : "Camera idle · WASD enabled in production viewer"}
    </div>
  );
}

export const CameraController = memo(CameraControllerComponent);
