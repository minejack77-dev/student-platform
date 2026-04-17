import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import vueDevTools from "vite-plugin-vue-devtools";

const HOST = "http://127.0.0.1:8000";
// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), vueDevTools()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    host: "127.0.0.1",
    proxy: {
      "^/api": {
        target: HOST,
        ws: true,
        changeOrigin: true,
      },
      "^/ws": {
        target: HOST,
        ws: true,
        changeOrigin: true,
      },

      "^/admin": {
        target: HOST,
        ws: true,
        changeOrigin: true,
        bypass: (req) => {
          if (req.headers && req.headers.referer)
            req.headers.referer = req.headers.referer.replace(
              "http://127.0.0.1:5173",
              HOST,
            );
          req.headers.host = req.headers.host.replace(
            "http://127.0.0.1:5173",
            HOST,
          );

          if (req.headers && req.headers.origin) {
            req.headers.origin = req.headers.origin.replace(
              "http://127.0.0.1:5173",
              HOST,
            );
          }
        },
      },
      "^/media": {
        target: HOST,
        ws: true,
        changeOrigin: true,
      },
      "^/static": {
        target: HOST,
        ws: true,
        changeOrigin: true,
      },
      "^/accounts/login": {
        target: HOST,
        ws: true,
        changeOrigin: true,
        bypass: (req) => {
          if (req.headers && req.headers.referer) {
            req.headers.referer = req.headers.referer.replace(
              "http://127.0.0.1:5173",
              HOST,
            );
          }
          req.headers.host = req.headers.host.replace("127.0.0.1:5173", HOST);

          if (req.headers && req.headers.origin) {
            req.headers.origin = req.headers.origin.replace(
              "http://127.0.0.1:5173",
              HOST,
            );
          }
        },
      },
    },
  },
});
