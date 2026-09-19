/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  assetPrefix: '/static/simple-ui',
  reactStrictMode: true,
  poweredByHeader: false,
  images: { unoptimized: true },
  experimental: {
    optimizePackageImports: ['radix-ui', '@json-render/react', 'streamdown'],
  },
}

export default nextConfig
