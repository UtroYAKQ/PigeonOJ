<script setup lang="ts">
import { Expand, Fold } from '@element-plus/icons-vue'
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
        :aria-label="t(appStore.collapsed ? 'sidebar.expand' : 'sidebar.collapse')"
        @click="appStore.toggleCollapsed()"
      >
        <n-icon size="18" :component="appStore.collapsed ? Expand : Fold" />
      </n-button>
    </template>
    {{ t(appStore.collapsed ? 'sidebar.expand' : 'sidebar.collapse') }}
  </n-tooltip>
</template>
