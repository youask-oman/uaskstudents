import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  async headers() {
    return [
      {
        source: "/share/:path*",
        headers: [
          { key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:9000/api/:path*',
      },
      {
        source: '/storage/:path*',
        destination: 'http://127.0.0.1:9000/storage/:path*',
      },
    ]
  },
  // Increase experimental proxy timeout for long-running AI requests
  experimental: {
    proxyTimeout: 120000, // 120 seconds for AI processing
  },
};

export default nextConfig;
