/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // 本地开发：/api 反代到后端，前端相对路径 /api/v1 即可直连，避免跨域；
    // 端口与后端配置链（.env SERVER_PORT / backend.toml [server] port）联动，
    // run-local.bat 启动时导出 SERVER_PORT，手动 npm run dev 回落后默认 8000
    proxy: {
      '/api': {
        target: `http://localhost:${process.env.SERVER_PORT ?? '8000'}`,
        changeOrigin: true,
      },
    },
  },
  test: {
    // dict.ts / http.ts 在模块加载期读取 localStorage，需要 DOM 环境；
    // 选 jsdom 而非 happy-dom：DOMPurify 在 happy-dom 下会误剥块级标签（环境缺陷，浏览器无此问题）
    environment: 'jsdom',
  },
})
