/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { NaiveUiResolver } from 'unplugin-vue-components/resolvers'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
    // naive-ui 按需组件注册（替代 main.ts 的 app.use(naive) 全量注册）：
    // 模板中的 <n-*> 组件在构建期自动注入具名 import，仅打包实际用到的组件
    Components({ resolvers: [NaiveUiResolver()], dts: 'src/types/components.d.ts' }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    rollupOptions: {
      output: {
        // 大依赖分包：主入口只含业务代码，vendor chunk 独立缓存（版本不变时命中缓存）
        manualChunks(id) {
          const path = id.replaceAll('\\', '/')
          if (!path.includes('node_modules')) return undefined
          if (path.includes('monaco-editor')) return 'monaco-editor'
          if (
            path.includes('/naive-ui/') ||
            path.includes('/@css-render/') ||
            path.includes('/vueuc/') ||
            path.includes('/seemly/') ||
            path.includes('/vdirs/') ||
            path.includes('/vooks/') ||
            path.includes('/treemate/') ||
            path.includes('/@juggle/resize-observer') ||
            path.includes('/date-fns/')
          ) {
            return 'naive-ui'
          }
          if (path.includes('md-editor-v3') || path.includes('/@codemirror/') || path.includes('/codemirror/') || path.includes('/mermaid/') || path.includes('/@lezer/')) {
            return 'md-editor'
          }
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
    // naive-ui 内部依赖 @juggle/resize-observer，其 Scheduler.stop 在 jsdom 的
    // 全局对象上缺 removeEventListener / dispatchEvent，组件卸载时抛错污染测试输出
    setupFiles: ['./src/test-setup.ts'],
  },
})
