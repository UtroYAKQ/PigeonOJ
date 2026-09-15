import { createPinia } from 'pinia'
import { createApp } from 'vue'
// Tailwind 先于组件库加载；Naive UI 通过 JS 主题对象注入，无全局 CSS 变量冲突
import '@/assets/main.css'
import '@/assets/monaco.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@fontsource/jetbrains-mono/700.css'

import App from './App.vue'
import { i18n } from './i18n'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)
// naive-ui 组件经 vite.config.ts 的 unplugin-vue-components + NaiveUiResolver
// 按需注册（构建期注入具名 import），不再全量 app.use(naive)
app.use(i18n)

app.mount('#app')
