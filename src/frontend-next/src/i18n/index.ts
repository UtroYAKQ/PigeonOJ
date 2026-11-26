import { createI18n } from 'vue-i18n'

import zhMessages from './locales/zh-CN'
import enMessages from './locales/en-US'

const savedLocale = localStorage.getItem('pigeonoj.locale')

export const i18n = createI18n<any, 'zh-CN' | 'en-US', false>({
  legacy: false,
  locale: savedLocale === 'en-US' ? 'en-US' : 'zh-CN',
  fallbackLocale: 'zh-CN',
  messages: { 'zh-CN': zhMessages, 'en-US': enMessages },
  // 缺 key 警告仅开发环境输出（vitest 的 MODE='test' 也静音，dict.spec 故意查未知键回退）
  missingWarn: import.meta.env.MODE === 'development',
  fallbackWarn: import.meta.env.MODE === 'development',
})

export function setLocale(locale: 'zh-CN' | 'en-US') {
  i18n.global.locale.value = locale
  localStorage.setItem('pigeonoj.locale', locale)
  window.dispatchEvent(new Event('pigeonoj:locale-change'))
}
