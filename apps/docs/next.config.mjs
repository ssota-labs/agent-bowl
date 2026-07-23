import { createMDX } from 'fumadocs-mdx/next';

/** @type {import('next').NextConfig} */
const config = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: '/docs/:path*.md', destination: '/md/:path*' }];
  },
};

const withMDX = createMDX();

export default withMDX(config);
