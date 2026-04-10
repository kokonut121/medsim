"use client";

import { memo, useRef } from "react";

import { AnnotationOverlay } from "@/components/viewer/AnnotationOverlay";
import { CameraController } from "@/components/viewer/CameraController";
import { useGaussianSplatViewer } from "@/hooks/useGaussianSplatViewer";
import type { Finding } from "@/types";

function SplatRendererComponent({
  signedUrl,
  findings,
  selectedLabel
}: {
  signedUrl: string;
  findings: Finding[];
  selectedLabel: string | null;
}) {
  /** Inner canvas container — viewer injects its canvas here; React never reconciles its children */
  const splatRef = useRef<HTMLDivElement | null>(null);
  const { loading: viewerLoading, error: viewerError } = useGaussianSplatViewer(
    signedUrl,
    splatRef,
  );

  return (
    <div className="panel viewer-stage" style={{ position: "relative" }}>
      {/* Viewer canvas container — React never adds children here */}
      <div
        ref={splatRef}
        style={{ position: "absolute", inset: 0 }}
      />

      {!signedUrl ? (
        <div className="viewer-placeholder">
          <div>
            <div className="eyebrow">World renderer</div>
            <h2 style={{ margin: "8px 0 12px" }}>Gaussian Splat Viewer</h2>
            <p className="muted" style={{ maxWidth: 520 }}>
              Waiting for a generated model asset before the renderer initializes.
            </p>
          </div>
        </div>
      ) : null}

      {signedUrl && viewerLoading ? (
        <div className="viewer-placeholder">
          <div>
            <div className="eyebrow">Loading world</div>
            <h2 style={{ margin: "8px 0 12px" }}>Preparing splat renderer</h2>
            <p className="muted" style={{ maxWidth: 520 }}>
              The model asset is downloading and initializing in the browser.
            </p>
          </div>
        </div>
      ) : null}

      <div style={{ position: "absolute", left: 24, right: 24, bottom: 24, display: "grid", gap: 12, pointerEvents: "none", zIndex: 10 }}>
        <div style={{ pointerEvents: "auto" }}>
          <CameraController selectedLabel={selectedLabel} />
        </div>
        <div className="pill" style={{ width: "fit-content", pointerEvents: "auto" }}>
          Asset URL: {signedUrl || "Awaiting model stream"}
        </div>
        {viewerError ? (
          <div className="pill" style={{ color: "var(--critical)", pointerEvents: "auto" }}>
            {viewerError}
          </div>
        ) : null}
      </div>

      <AnnotationOverlay findings={findings} />
    </div>
  );
}

export const SplatRenderer = memo(SplatRendererComponent);
