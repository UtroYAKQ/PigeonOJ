<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { setLocale } from '@/i18n'

const { locale, t } = useI18n()
const current = computed(() => locale.value)

function change(value: 'zh-CN' | 'en-US') {
  setLocale(value)
}
</script>

<template>
  <el-dropdown trigger="click" @command="change">
    <el-button text class="language-switcher" :aria-label="t('app.language')">
      <span class="language-switcher__globe">🌐</span>{{ current === 'zh-CN' ? t('app.localeZh') : 'EN' }}
    </el-button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="zh-CN" :disabled="current === 'zh-CN'">{{ t('app.localeZh') }}</el-dropdown-item>
        <el-dropdown-item command="en-US" :disabled="current === 'en-US'">{{ t('app.localeEn') }}</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<style scoped>
.language-switcher { color: var(--el-text-color-regular); }
.language-switcher__globe { margin-right: 4px; }
</style>
