"use client";

import { type RefObject, useEffect, useRef, useState } from "react";

import { isSplatAssetUrl } from "@/lib/splat";

import type { Viewer } from "@mkkellogg/gaussian-splats-3d";

function removeManagedMount(
  container: HTMLDivElement,
  mount: HTMLDivElement,
) {
  if (mount.parentNode === container) {
    mount.remove();
  }
}

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
    const mount = document.createElement("div");
    mount.style.position = "absolute";
    mount.style.inset = "0";
    container.replaceChildren(mount);

    let viewer: Viewer | null = null;
    let cleanedUp = false;

    const teardown = () => {
      if (cleanedUp) {
        return;
      }
      cleanedUp = true;

      const activeViewer = viewer;
      viewer = null;
      if (viewerRef.current === activeViewer) {
        viewerRef.current = null;
      }

      if (activeViewer) {
        try {
          activeViewer.stop();
        } catch {
          // Best-effort teardown only.
        }
        try {
          activeViewer.dispose();
        } catch (disposeError) {
          console.warn("Gaussian splat viewer cleanup raced with DOM teardown", disposeError);
        }
      }

      removeManagedMount(container, mount);
    };

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

        viewer = new GS3D.Viewer({
          rootElement: mount,
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
          teardown();
          return;
        }

        viewer.start();
        viewerRef.current = viewer;
        setError(null);
      } catch (loadError) {
        teardown();
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
      teardown();
    };
  }, [containerRef, signedUrl]);

  return { viewerRef, loading, error };
}
