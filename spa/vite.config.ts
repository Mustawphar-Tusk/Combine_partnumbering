import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The SPA is served by FastAPI under /app (static mount), so assets must be
// referenced with that base. In dev (vite dev server) the same base is used and
// API calls are proxied to the FastAPI backend on :8080.
export default defineConfig({
  base: "/app/",
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
      },
    },
  },
});
