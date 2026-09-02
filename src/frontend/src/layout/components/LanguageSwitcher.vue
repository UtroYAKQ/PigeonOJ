<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { setLocale } from '@/i18n'

const { locale, t } = useI18n()

const options = computed(() => [
  { label: t('app.localeZh'), key: 'zh-CN', disabled: locale.value === 'zh-CN' },
  { label: t('app.localeEn'), key: 'en-US', disabled: locale.value === 'en-US' },
])

function change(key: string) {
  if (key === 'zh-CN' || key === 'en-US') setLocale(key)
}
</script>

<template>
  <n-dropdown trigger="click" :options="options" @select="change">
    <n-button quaternary size="small" :aria-label="t('app.language')">
      {{ locale === 'zh-CN' ? t('app.localeZh') : 'EN' }}
    </n-button>
  </n-dropdown>
</template>

<style scoped>
.language-switcher__globe {
  margin-right: 4px;
}
</style>
