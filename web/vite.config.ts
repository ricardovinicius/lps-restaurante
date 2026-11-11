import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => ({
  server: {
    proxy: {
      "/api": loadEnv(mode, ".", "MESA_").MESA_GATEWAY_URL || "http://127.0.0.1:8080",
    },
  },
}));
