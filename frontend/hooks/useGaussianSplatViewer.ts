"use client";

import { type RefObject, useEffect, useRef, useState } from "react";

import { isSplatAssetUrl } from "@/lib/splat";

import type { Viewer } from "@mkkellogg/gaussian-splats-3d";

export function useGaussianSplatViewer(
  signedUrl: string,
  containerRef: RefObject<HTMLDivElement | null>,
) {
  const viewerRef = useRef<Viewer | null>(null);
  const [loading, setLoading] = useState(Boolean(signedUrl));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const container = containerRef.current;

    if (!signedUrl || !container) {
      setLoading(false);
      setError(null);
      return;
    }

    let disposed = false;

    const load = async () => {
      try {
        setLoading(true);

        const GS3D = (await import("@mkkellogg/gaussian-splats-3d")) as {
          Viewer: new (options?: Record<string, unknown>) => Viewer;
          SceneFormat?: { Spz?: number | string };
        };

        if (disposed) {
          return;
        }

        const viewer = new GS3D.Viewer({
          rootElement: container,
          cameraUp: [0, -1, 0],
          initialCameraPosition: [0, 1, 3],
          initialCameraLookAt: [0, 0.5, 0],
          gpuAcceleratedSort: false,
          sharedMemoryForWorkers: false,
          antialiased: true,
        });

        await viewer.addSplatScene(signedUrl, {
          format: isSplatAssetUrl(signedUrl) ? GS3D.SceneFormat?.Spz : undefined,
          showLoadingUI: false,
          splatAlphaRemovalThreshold: 1,
        });

        if (disposed) {
          viewer.dispose();
          return;
        }

        viewer.start();
        viewerRef.current = viewer;
        setError(null);
      } catch (loadError) {
        if (!disposed) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to render Gaussian splat",
          );
        }
      } finally {
        if (!disposed) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      disposed = true;
      viewerRef.current?.stop();
      viewerRef.current?.dispose();
      viewerRef.current = null;
    };
  }, [containerRef, signedUrl]);

  return { viewerRef, loading, error };
}
