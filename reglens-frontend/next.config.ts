import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Pin the workspace root — the umbrella repo has sibling lockfiles.
  turbopack: { root: __dirname },
  serverExternalPackages: ["@copilotkit/runtime"],
  env: {
    // Self-hosted: managed Intelligence Threads are disabled.
    NEXT_PUBLIC_COPILOTKIT_THREADS_ENABLED: "false",
  },
  typescript: {
    // LangGraphHttpAgent has a structural type mismatch with CopilotRuntime's
    // agent map generic; runtime behavior is correct.
    ignoreBuildErrors: true,
  },
};

export default nextConfig;
