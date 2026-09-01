<script setup lang="ts">
import { Moon, Sunny } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'

import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
const { t } = useI18n()
</script>

<template>
  <n-tooltip trigger="hover" placement="bottom">
    <template #trigger>
      <n-button
        quaternary
        size="small"
        :aria-label="t('profile.theme')"
        @click="appStore.toggleTheme()"
      >
        <n-icon size="16" :component="appStore.isDark ? Sunny : Moon" />
      </n-button>
    </template>
    {{ appStore.isDark ? t('profile.light') : t('profile.dark') }}
  </n-tooltip>
</template>
