<script setup lang="ts">
import { computed } from 'vue'

import { useAppStore } from '@/stores/app'
import { isRenderableLogo } from '@/utils/logo'

const appStore = useAppStore()
const name = computed(() => appStore.siteConfig.name || 'PigeonOJ')
// 外链 URL 或站内文件 URL 直接渲染；空值 / 不可识别形态回退默认图标
const logoUrl = computed(() =>
  isRenderableLogo(appStore.siteConfig.logo) ? appStore.siteConfig.logo : '',
)
</script>

<template>
  <router-link class="side-logo" :class="{ collapsed: appStore.collapsed }" to="/">
    <img v-if="logoUrl" class="side-logo__img" :src="logoUrl" :alt="name" />
    <span v-else class="side-logo__mark">🐦</span>
    <h2 v-if="!appStore.collapsed" class="side-logo__title">{{ name }}</h2>
  </router-link>
</template>

<style scoped>
.side-logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-shrink: 0;
  text-decoration: none;
}
.side-logo__mark {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  font-size: 20px;
  color: var(--app-primary);
  background: var(--app-muted-bg);
}
.side-logo__img {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  object-fit: contain;
}
.side-logo__title {
  margin: 0;
  max-width: 150px;
  overflow: hidden;
  white-space: nowrap;
  font-size: 16px;
  font-weight: 700;
  color: var(--app-primary);
}
.side-logo.collapsed .side-logo__mark {
  width: 32px;
  height: 32px;
  font-size: 18px;
}
</style>
