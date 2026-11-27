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
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const path = id.replaceAll('\\', '/')
          // Vite 注入的 preload helper 是虚拟模块（\0vite/preload-helper）：
          // 不单独拆出时会被 Rollup 分配进 monaco chunk，入口（有路由懒加载）随即
          // 静态 import 该 chunk，最终 3MB 的 monaco 被首屏 modulepreload 全量加载
          if (path.includes('vite/preload-helper')) return 'preload-helper'
          if (!path.includes('node_modules')) return undefined
          if (path.includes('monaco-editor')) return 'monaco-editor'
          if (path.includes('/katex/')) return 'katex'
          if (
            path.includes('/@vue/') ||
            path.includes('/vue/') ||
            path.includes('vue-router') ||
            path.includes('/pinia/') ||
            path.includes('vue-i18n') ||
            path.includes('/@intlify/') ||
            path.includes('/@vueuse/') ||
            path.includes('/axios/')
          ) {
            return 'vue-vendor'
          }
          return undefined
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: `http://localhost:${process.env.SERVER_PORT ?? '8000'}`,
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
  },
})
