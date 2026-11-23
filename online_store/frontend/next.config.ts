import type { NextConfig } from "next";

/**
 * In Docker, Nginx routes `/api` and `/media` to FastAPI, so the browser only ever
 * talks to one origin. For `npm run dev` without Nginx, set API_PROXY_TARGET
 * (e.g. http://localhost:8000) and Next.js forwards those paths instead.
 */
const apiProxyTarget = process.env.API_PROXY_TARGET;

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  async rewrites() {
    if (!apiProxyTarget) return [];
    return [
      { source: "/api/:path*", destination: `${apiProxyTarget}/api/:path*` },
      { source: "/media/:path*", destination: `${apiProxyTarget}/media/:path*` },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
