import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import vueDevTools from "vite-plugin-vue-devtools";

const HOST = "http://127.0.0.1:8000";
const BACKEND_URL = new URL(HOST);

const rewriteProxyHeaders = (req) => {
  if (req.headers?.referer) {
    try {
      const refererUrl = new URL(req.headers.referer);
      refererUrl.protocol = BACKEND_URL.protocol;
      refererUrl.host = BACKEND_URL.host;
      req.headers.referer = refererUrl.toString();
    } catch (_error) {
      // Keep the original referer if it is not a valid absolute URL.
    }
  }

  if (req.headers?.host) {
    req.headers.host = BACKEND_URL.host;
  }

  if (req.headers?.origin) {
    req.headers.origin = BACKEND_URL.origin;
  }
};
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
          rewriteProxyHeaders(req);
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
          rewriteProxyHeaders(req);
        },
      },
    },
  },
});
