declare module "@mkkellogg/gaussian-splats-3d" {
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
  }
}
