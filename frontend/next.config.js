/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/pcs/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/pcs/:path*`,
      },
      {
        source: '/api/users/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/users/:path*`,
      },
      {
        source: '/api/auth/user-permissions',
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/auth/user-permissions`,
      },
      {
        source: '/api/auth/me',
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/auth/me`,
      },
      {
        source: '/api/auth/validate',
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/auth/validate`,
      },
    ]
  },
}

export default nextConfig
