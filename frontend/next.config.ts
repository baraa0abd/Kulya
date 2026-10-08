import type { NextConfig } from "next";

// The browser only ever talks to this origin; /api is proxied to Django, so there is no CORS
// surface and the backend URL never reaches the client bundle.
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  trailingSlash: true, // Django REST endpoints end in a slash
  async rewrites() {
    return [{ source: "/api/:path*/", destination: `${backend}/api/:path*/` }];
  },
  turbopack: {
    rules: { "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" } },
  },
};

export default nextConfig;
