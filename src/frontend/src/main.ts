import { createPinia } from 'pinia'
import { createApp } from 'vue'
import naive from 'naive-ui'
// Tailwind 先于组件库加载；Naive UI 通过 JS 主题对象注入，无全局 CSS 变量冲突
import '@/assets/main.css'

import App from './App.vue'
import { i18n } from './i18n'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(naive)
app.use(i18n)

app.mount('#app')
