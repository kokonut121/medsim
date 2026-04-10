"use client";

import { useEffect, useRef, useState } from "react";

import { AnnotationOverlay } from "@/components/viewer/AnnotationOverlay";
import { CameraController } from "@/components/viewer/CameraController";
import type { Finding } from "@/types";

/** Return true for any URL that points to a .spz asset (including proxy stream routes) */
function isSpzUrl(url: string): boolean {
  return (
    url.endsWith(".spz") ||
    url.endsWith(".bin") ||
    url.includes("/splat/stream") ||
    url.includes("/splat/")
  );
}

export function SplatRenderer({
  signedUrl,
  findings,
  selectedLabel
}: {
  signedUrl: string;
  findings: Finding[];
  selectedLabel: string | null;
}) {
  /** Outer shell — React-owned; used only for layout / size queries */
  const shellRef = useRef<HTMLDivElement | null>(null);
  /** Inner canvas container — viewer injects its canvas here; React never reconciles its children */
  const splatRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<{
    start: () => void;
    stop?: () => void;
    dispose?: () => void;
  } | null>(null);

  const [viewerError, setViewerError] = useState<string | null>(null);
  const [viewerLoading, setViewerLoading] = useState(false);

  useEffect(() => {
    if (!signedUrl || !splatRef.current) {
      setViewerLoading(false);
      setViewerError(null);
      return;
    }

    const splatEl = splatRef.current;
    let disposed = false;

    const load = async () => {
      try {
        setViewerLoading(true);
        // ⚠ Do NOT call replaceChildren() — React doesn't own splatEl's children
        // but calling replaceChildren on cleanup races with React's reconciler and
        // causes "removeChild: node is not a child" errors.

        const GS3D = await import("@mkkellogg/gaussian-splats-3d") as {
          Viewer: new (options?: Record<string, unknown>) => {
            addSplatScene: (path: string, options?: Record<string, unknown>) => Promise<void>;
            start: () => void;
            stop?: () => void;
            dispose?: () => void;
          };
          SceneFormat?: { Spz?: number | string };
        };

        if (disposed) return;

        const viewer = new GS3D.Viewer({
          rootElement:            splatEl,
          cameraUp:               [0, 1, 0],
          initialCameraPosition:  [0, 1, 3],
          initialCameraLookAt:    [0, 0.5, 0],
          gpuAcceleratedSort:     true,
          sharedMemoryForWorkers: false,
          antialiased:            true,
        });

        await viewer.addSplatScene(signedUrl, {
          format:                     isSpzUrl(signedUrl) ? GS3D.SceneFormat?.Spz : undefined,
          showLoadingUI:              false,
          splatAlphaRemovalThreshold: 1,
        });

        if (disposed) { viewer.dispose?.(); return; }

        viewer.start();
        viewerRef.current = viewer;
        setViewerError(null);
      } catch (error) {
        if (!disposed) {
          setViewerError(error instanceof Error ? error.message : "Unable to render Gaussian splat");
        }
      } finally {
        if (!disposed) setViewerLoading(false);
      }
    };

    void load();

    return () => {
      disposed = true;
      viewerRef.current?.stop?.();
      viewerRef.current?.dispose?.();
      viewerRef.current = null;
      // ⚠ Do NOT call replaceChildren() after dispose — same race condition risk
    };
  }, [signedUrl]);

  return (
    <div ref={shellRef} className="panel viewer-stage" style={{ position: "relative" }}>
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
