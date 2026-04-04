"use client";

import { AnnotationOverlay } from "@/components/viewer/AnnotationOverlay";
import { CameraController } from "@/components/viewer/CameraController";
import type { Finding } from "@/types";

export function SplatRenderer({
  signedUrl,
  findings,
  selectedLabel
}: {
  signedUrl: string;
  findings: Finding[];
  selectedLabel: string | null;
}) {
  return (
    <div className="panel viewer-stage">
      <div className="mock-splat">
        <div>
          <div className="eyebrow">SparkJS stream target</div>
          <h2 style={{ margin: "8px 0 12px" }}>Gaussian Splat Viewer</h2>
          <p className="muted" style={{ maxWidth: 520 }}>
            This scaffold reserves the exact viewer surface described in the PRD: a large splat canvas,
            in-scene annotations, and camera fly-to orchestration.
          </p>
          <p className="muted">Signed URL: {signedUrl || "Awaiting model stream"}</p>
          <CameraController selectedLabel={selectedLabel} />
        </div>
      </div>
      <AnnotationOverlay findings={findings} />
    </div>
  );
}

