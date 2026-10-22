import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "prompt",
      includeAssets: ["favicon.svg", "icons/*.png"],
      manifest: {
              id: mode === "admin" ? "/?app=admin" : "/",
              name: mode === "admin" ? "Signal Engine Operator" : "Signal Engine",
              short_name: mode === "admin" ? "SE Operator" : "Signal Engine",
              description: mode === "admin" ? "Private Signal Engine operator workspace" : "Market research and paper-signal monitoring",
              theme_color: "#f6f4f0",
              background_color: "#f6f4f0",
              display: "standalone",
              scope: "/",
              start_url: mode === "admin" ? "/?app=admin" : "/",
              icons: [
                {
                  src: "/icons/icon-192.png",
                  sizes: "192x192",
                  type: "image/png",
                  purpose: "any",
                },
                {
                  src: "/icons/icon-512.png",
                  sizes: "512x512",
                  type: "image/png",
                  purpose: "any maskable",
                },
              ],
            },
      workbox: {
              globPatterns: ["**/*.{js,css,html,png,svg,woff2}"],
              navigateFallback: "/index.html",
              navigateFallbackDenylist: [
                /^\/api\//,
                /^\/auth\//,
                /^\/ws\//,
                /^\/webhook\//,
              ],
              cleanupOutdatedCaches: true,
              importScripts: ["/sw-cleanup.js"],
            },
      devOptions: { enabled: false },
          }),
  ],
  cacheDir: "node_modules/.vite-" + mode,
  optimizeDeps: { exclude: ["virtual:pwa-register/react"] },
  define: {
    __APP_TARGET__: JSON.stringify(mode === "admin" ? "admin" : "public"),
  },
  build: {
    outDir: mode === "admin" ? "dist/admin" : "dist/public",
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (/recharts|d3-|victory/.test(id)) return "charts";
            if (/gsap/.test(id)) return "motion";
            return "vendor";
          }
        },
      },
    },
  },
  server: {
    host: "127.0.0.1",
    proxy: Object.fromEntries(
      ["/api", "/auth", "/ws", "/webhook"].map((path) => [
        path,
        { target: "http://127.0.0.1:8000", ws: true, changeOrigin: false },
      ]),
    ),
  },
  preview: { host: "127.0.0.1" },
}));
