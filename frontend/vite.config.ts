import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8123", changeOrigin: false },
    },
  },
  build: {
    outDir: "../agent_umimiy/static/web",
    emptyOutDir: true,
    sourcemap: false,
  },
});
