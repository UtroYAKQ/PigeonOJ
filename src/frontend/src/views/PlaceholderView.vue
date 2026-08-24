<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

const route = useRoute()
const { t } = useI18n()
const placeholder = computed(() => route.meta.placeholder)
const title = computed(() =>
  placeholder.value?.titleKey
    ? t(String(placeholder.value.titleKey))
    : (placeholder.value?.title ??
      (route.meta.titleKey
        ? t(String(route.meta.titleKey))
        : (route.meta.title ?? t('placeholder.title')))),
)
const description = computed(() =>
  placeholder.value?.descriptionKey
    ? t(String(placeholder.value.descriptionKey))
    : (placeholder.value?.description ?? t('placeholder.description')),
)
const endpoints = computed(() => placeholder.value?.endpoints ?? [])
</script>

<template>
  <n-card :title="t('placeholder.developing', { title })" :bordered="false">
    <p class="placeholder__desc">{{ description }}</p>
    <n-empty size="large" :description="t('placeholder.description')" />
    <n-descriptions
      v-if="endpoints.length"
      :column="1"
      bordered
      class="placeholder__endpoints"
      :title="t('placeholder.endpoints')"
    >
      <n-descriptions-item v-for="e in endpoints" :key="e" :label="e.split(' ')[0]">
        <code>{{ e.split(' ').slice(1).join(' ') }}</code>
      </n-descriptions-item>
    </n-descriptions>
  </n-card>
</template>

<style scoped>
.placeholder__desc {
  color: var(--app-text-secondary);
  max-width: 560px;
  margin: 0 auto 16px;
}
.placeholder__endpoints {
  max-width: 560px;
  margin: 16px auto 0;
  text-align: left;
}
</style>
