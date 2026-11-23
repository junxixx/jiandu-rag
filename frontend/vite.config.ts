import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { VitePWA } from "vite-plugin-pwa";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: [],
      manifest: {
        name: "问牍·青声 —— RAG与多角色AI驱动的简牍社交学习平台",
        short_name: "问牍·青声",
        description: "RAG与多角色AI驱动的简牍社交学习平台",
        theme_color: "#7c3a21",
        background_color: "#f6ecda",
        display: "standalone",
        start_url: "/",
        lang: "zh-CN",
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,svg,woff2}"],
        navigateFallback: "index.html",
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.loli\.net\/.*/i,
            handler: "CacheFirst",
            options: {
              cacheName: "dj-fonts",
              expiration: { maxEntries: 6, maxAgeSeconds: 60 * 60 * 24 * 365 },
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
      },
    },
  },
});
