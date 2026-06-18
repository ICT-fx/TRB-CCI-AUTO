/** @type {import('next').NextConfig} */
const nextConfig = {
  // sharp is a native dependency used only on the server (TIFF -> PNG conversion).
  serverExternalPackages: ["sharp"],
};

export default nextConfig;
