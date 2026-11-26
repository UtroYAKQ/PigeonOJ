<script setup lang="ts">
import { Megaphone } from '@lucide/vue'
import { useI18n } from 'vue-i18n'

import MarkdownView from '@/components/common/MarkdownView.vue'
import { formatDateTime } from '@/utils/format'

defineProps<{
  source: string | null | undefined
  updatedAt?: string | null
}>()

const { t } = useI18n()
</script>

<template>
  <section class="rounded-xl border border-border bg-card p-4">
    <header class="flex flex-wrap items-baseline justify-between gap-2 pb-2.5">
      <h2 class="flex items-center gap-2 text-[13.5px] font-semibold">
        <Megaphone class="size-4 text-muted-foreground" />
        {{ t('contests.detail.announcement') }}
      </h2>
      <span v-if="updatedAt" class="text-[11.5px] tabular-nums text-muted-foreground">
        {{ t('contests.detail.announcementUpdatedAt') }} {{ formatDateTime(updatedAt) }}
      </span>
    </header>
    <MarkdownView :source="source" />
  </section>
</template>
