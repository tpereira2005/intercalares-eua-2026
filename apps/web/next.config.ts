import type { NextConfig } from "next";

const config: NextConfig = {
  // Export estático: o site inteiro é servido como ficheiros pelo Worker.
  output: "export",
  trailingSlash: true,
  reactStrictMode: true,
  poweredByHeader: false,
  images: { unoptimized: true },
};

export default config;
