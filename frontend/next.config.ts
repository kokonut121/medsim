import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  typedRoutes: true,
  // gaussian-splats-3d ships as "type":"module" ESM — webpack needs to transpile it
  transpilePackages: ["@mkkellogg/gaussian-splats-3d"],
};

export default nextConfig;
