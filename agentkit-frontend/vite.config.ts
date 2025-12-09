import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

// Point to agentkit-backend (port 8005) instead of RAG service (port 8001)
const backendTarget = process.env.BACKEND_URL ?? "http://localhost:8002";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5171,
    proxy: {
      "/support": {
        target: backendTarget,
        changeOrigin: true,
      },
    },
    // For production deployments, you need to add your public domains to this list
    allowedHosts: [
      // You can remove these examples added just to demonstrate how to configure the allowlist
      ".ngrok.io",
      ".trycloudflare.com",
      ".ngrok-free.app",
    ],
  },
});

