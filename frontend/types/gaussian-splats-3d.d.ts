declare module "@mkkellogg/gaussian-splats-3d" {
  import type * as THREE from "three";

  export const SceneFormat: {
    Ply: number | string;
    Splat: number | string;
    KSplat: number | string;
    Spz: number | string;
  };

  export class Viewer {
    constructor(options?: Record<string, unknown>);
    addSplatScene(path: string, options?: Record<string, unknown>): Promise<void>;
    start(): void;
    stop(): void;
    dispose(): void;
    /** Three.js perspective camera — readable every frame for annotation projection */
    camera: THREE.PerspectiveCamera;
    /** Underlying WebGL renderer */
    renderer: THREE.WebGLRenderer;
  }
}
