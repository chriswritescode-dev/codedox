import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import tailwindcss from "@tailwindcss/vite";


// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  // Set the third parameter to '' to load all env regardless of the `VITE_` prefix.
  const env = loadEnv(mode, process.cwd(), '')
  
  // Use environment variable for proxy target with fallback
  const proxyTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'
  const wsProxyTarget = proxyTarget.replace(/^http/, 'ws')
  
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      host: "0.0.0.0",
      port: 5173,
      allowedHosts: true,
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
          // Don't rewrite the path - keep the /api prefix
        },
        "/ws": {
          target: wsProxyTarget,
          ws: true,
        },
      },
    },
  };
})