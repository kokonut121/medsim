"use client";

import { useEffect, useRef, useState } from "react";

import { AnnotationOverlay } from "@/components/viewer/AnnotationOverlay";
import { CameraController } from "@/components/viewer/CameraController";
import type { Finding } from "@/types";

type SplatViewer = {
  addSplatScene: (path: string, options?: Record<string, unknown>) => Promise<void>;
  start: () => void;
  stop?: () => void;
  dispose?: () => void;
};

type GaussianSplatsModule = {
  Viewer: new (options?: Record<string, unknown>) => SplatViewer;
  SceneFormat?: {
    Spz?: number | string;
  };
};

function inferSceneFormat(signedUrl: string, sceneFormat: GaussianSplatsModule["SceneFormat"]) {
  if (signedUrl.endsWith(".spz") || signedUrl.endsWith(".bin")) {
    return sceneFormat?.Spz;
  }
  return undefined;
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
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [viewerError, setViewerError] = useState<string | null>(null);
  const [viewerLoading, setViewerLoading] = useState(false);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const container = containerRef.current;
    let disposed = false;
    let viewer: SplatViewer | null = null;

    if (!signedUrl) {
      container.replaceChildren();
      setViewerLoading(false);
      setViewerError(null);
      return;
    }

    const load = async () => {
      try {
        setViewerLoading(true);
        container.replaceChildren();
        container.style.width = "100%";
        container.style.height = "100%";

        const GaussianSplats3D = (await import("@mkkellogg/gaussian-splats-3d")) as GaussianSplatsModule;
        if (disposed) {
          return;
        }
        viewer = new GaussianSplats3D.Viewer({
          rootElement: container,
          cameraUp: [0, -1, -0.6],
          initialCameraPosition: [-1, -2, 5],
          initialCameraLookAt: [0, 1, 0]
        });
        await viewer.addSplatScene(signedUrl, {
          format: inferSceneFormat(signedUrl, GaussianSplats3D.SceneFormat),
          showLoadingUI: false,
          splatAlphaRemovalThreshold: 5,
          position: [0, 1, 0],
          scale: [1.2, 1.2, 1.2]
        });
        viewer.start();
        setViewerError(null);
      } catch (error) {
        if (!disposed) {
          setViewerError(error instanceof Error ? error.message : "Unable to render Gaussian splat");
        }
      } finally {
        if (!disposed) {
          setViewerLoading(false);
        }
      }
    };

    void load();

    return () => {
      disposed = true;
      viewer?.stop?.();
      viewer?.dispose?.();
      container.replaceChildren();
    };
  }, [signedUrl]);

  return (
    <div className="panel viewer-stage">
      <div className="viewer-canvas" ref={containerRef} />
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
      <div style={{ position: "absolute", left: 24, right: 24, bottom: 24, display: "grid", gap: 12, pointerEvents: "none" }}>
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
