"use client";

export function CameraController({ selectedLabel }: { selectedLabel: string | null }) {
  return (
    <div className="pill">
      {selectedLabel ? `Camera fly-to: ${selectedLabel}` : "Camera idle · WASD enabled in production viewer"}
    </div>
  );
}

