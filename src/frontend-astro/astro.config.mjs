// @ts-check
import tailwindcss from "@tailwindcss/vite"
import { defineConfig } from "astro/config"
import react from "@astrojs/react"

/**
 * 开发期把 /api 代理到后端，避免浏览器跨域。
 * 端口链与旧前端一致：API_PROXY_TARGET > SERVER_PORT > 8000。
 * 生产由 nginx 反代 /api（见 nginx.conf）。
 */
const backendPort = process.env.SERVER_PORT ?? "8000"
const backendTarget =
  process.env.API_PROXY_TARGET ?? `http://localhost:${backendPort}`

// https://astro.build/config
export default defineConfig({
  output: "static",
  devToolbar: { enabled: false },
  vite: {
    plugins: [tailwindcss()],
    server: {
      proxy: {
        "/api": {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
  },
  integrations: [react()],
})
