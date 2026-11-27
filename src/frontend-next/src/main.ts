import { createPinia } from 'pinia'
import { createApp } from 'vue'

import '@/assets/main.css'

import 'vue-sonner/style.css'

import App from './App.vue'
import { i18n } from './i18n'
import router from './router'

createApp(App).use(createPinia()).use(router).use(i18n).mount('#app')
