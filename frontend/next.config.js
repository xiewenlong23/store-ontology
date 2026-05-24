/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: [
    '@copilotkit/react-core',
    '@copilotkit/react-ui',
    '@copilotkit/runtime',
    '@copilotkit/shared',
    '@copilotkit/runtime-client-gql',
    '@ag-ui/client',
    '@ag-ui/core',
    '@ag-ui/langgraph',
  ],
  webpack: (config, { isServer }) => {
    config.module.rules.push({
      test: /\.mjs$/,
      include: /node_modules\/@copilotkit|node_modules\/@ag-ui/,
      type: 'javascript/auto',
    });
    return config;
  },
}

module.exports = nextConfig
