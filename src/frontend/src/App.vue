<script setup lang="ts">
import { computed, watch } from 'vue'
import { dateEnUS, dateZhCN, darkTheme, enUS, zhCN } from 'naive-ui'
import { useI18n } from 'vue-i18n'

import { refreshDocumentTitle } from '@/router'
import { themeOverrides } from '@/settings/theme'
import { useAppStore } from '@/stores/app'

const { locale } = useI18n()
const appStore = useAppStore()

// 站点配置（名称 / Logo / ICP / 默认主题 / 注册开关）异步加载，失败保持内置兜底值；
// 站点名到达后刷新浏览器标签标题
appStore.loadSiteConfig()
watch(
  () => appStore.siteConfig.name,
  () => refreshDocumentTitle(),
)

const naiveTheme = computed(() => (appStore.isDark ? darkTheme : undefined))
const naiveLocale = computed(() => (locale.value === 'en-US' ? enUS : zhCN))
const naiveDateLocale = computed(() => (locale.value === 'en-US' ? dateEnUS : dateZhCN))
</script>

<template>
  <n-config-provider
    class="app-root"
    :theme="naiveTheme"
    :theme-overrides="themeOverrides"
    :locale="naiveLocale"
    :date-locale="naiveDateLocale"
  >
    <n-message-provider
      ><n-dialog-provider><router-view /></n-dialog-provider
    ></n-message-provider>
  </n-config-provider>
</template>

<style scoped>
.app-root {
  height: 100dvh;
}
</style>
