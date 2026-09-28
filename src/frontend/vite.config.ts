import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "fs";
import path from "path";

function copyMaplibreWorker() {
  return {
    name: "copy-maplibre-worker",
    buildStart() {
      const srcDir = path.resolve(__dirname, "node_modules/maplibre-gl/dist");
      const destDir = path.resolve(__dirname, "public/assets");
      if (fs.existsSync(srcDir)) {
        if (!fs.existsSync(destDir)) {
          fs.mkdirSync(destDir, { recursive: true });
        }
        const files = [
          "maplibre-gl-worker.mjs",
          "maplibre-gl-shared.mjs",
          "maplibre-gl-worker-dev.mjs",
          "maplibre-gl-shared-dev.mjs",
        ];
        for (const file of files) {
          const src = path.join(srcDir, file);
          const dest = path.join(destDir, file);
          if (fs.existsSync(src)) {
            fs.copyFileSync(src, dest);
          }
        }
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), copyMaplibreWorker()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/health": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  optimizeDeps: {
    exclude: ["maplibre-gl"],
  },
});

