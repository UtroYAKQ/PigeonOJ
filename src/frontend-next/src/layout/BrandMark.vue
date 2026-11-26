<script setup lang="ts">
import { computed } from 'vue'

import { useAppStore } from '@/stores/app'
import { isRenderableLogo } from '@/utils/logo'

const DEFAULT_MARK = '/brand/pigeon-mark.png'

withDefaults(defineProps<{ size?: 'sm' | 'md' }>(), { size: 'md' })

const appStore = useAppStore()
const logoUrl = computed(() =>
  isRenderableLogo(appStore.siteConfig.logo) ? appStore.siteConfig.logo : '',
)
</script>

<template>
  <!-- 不加底色 / 描边：Logo 自身透明底，直接落在所在容器背景上，避免色块盖住图形 -->
  <span class="grid shrink-0 place-items-center" :class="size === 'sm' ? 'size-8' : 'size-9'">
    <img v-if="logoUrl" :src="logoUrl" :alt="appStore.siteName" class="size-full object-contain" />
    <img
      v-else
      :src="DEFAULT_MARK"
      :alt="appStore.siteName"
      class="size-full object-contain p-0.5 dark:invert"
    />
  </span>
</template>
