import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    ...(mode === "public"
      ? [
          VitePWA({
            registerType: "prompt",
            includeAssets: ["favicon.svg", "icons/*.png"],
            manifest: {
              id: "/",
              name: "Signal Engine",
              short_name: "Signal Engine",
              description: "Market research and paper-signal monitoring",
              theme_color: "#141714",
              background_color: "#f4f3ee",
              display: "standalone",
              scope: "/",
              start_url: "/",
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
        ]
      : []),
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
  },
  server: {
    host: "127.0.0.1",
    proxy: Object.fromEntries(
      ["/api", "/auth", "/ws"].map((path) => [
        path,
        { target: "http://127.0.0.1:8000", ws: true, changeOrigin: false },
      ]),
    ),
  },
  preview: { host: "127.0.0.1" },
}));
