<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { FileText } from '@lucide/vue'

import MarkdownView from '@/components/common/MarkdownView.vue'
import { formatDateTime } from '@/utils/format'
import type { ProblemSetDetail } from '@/types'

defineProps<{
  detail: ProblemSetDetail
  solved: number
  total: number
  percent: number
}>()

const { t } = useI18n()
</script>

<template>
  <div class="grid gap-4 lg:grid-cols-[minmax(0,7fr)_minmax(0,3fr)]">
    <section class="overflow-hidden rounded-xl border border-border bg-card">
      <header class="border-b border-border/70 px-4 py-2.5 text-[13px] font-semibold">
        {{ t('problemSets.list.descLabel') }}
      </header>
      <div class="px-4 py-4">
        <MarkdownView v-if="detail.description" :source="detail.description" />
        <div
          v-else
          class="flex min-h-[220px] flex-col items-center justify-center gap-2 text-muted-foreground"
        >
          <FileText class="size-7" :stroke-width="1.5" />
          <p class="text-sm">{{ t('problemSets.detail.noDescription') }}</p>
        </div>
      </div>
    </section>

    <aside class="self-start overflow-hidden rounded-xl border border-border bg-card">
      <header class="border-b border-border/70 px-4 py-2.5 text-[13px] font-semibold">
        {{ t('problemSets.detail.infoTitle') }}
      </header>

      <dl class="divide-y divide-border/70 px-4 text-[13px]">
        <div class="flex items-center justify-between gap-3 py-2.5">
          <dt class="shrink-0 text-muted-foreground">
            {{ t('problemSets.detail.ownerLabelPlain') }}
          </dt>
          <dd class="truncate text-right font-medium">{{ detail.owner_name || '--' }}</dd>
        </div>
        <div class="flex items-center justify-between gap-3 py-2.5">
          <dt class="shrink-0 text-muted-foreground">{{ t('problemSets.list.createdAt') }}</dt>
          <dd class="text-right tabular-nums">{{ formatDateTime(detail.created_at) }}</dd>
        </div>
      </dl>

      <div class="border-t border-border/70 px-4 pb-4 pt-3">
        <div class="flex items-center justify-between pb-2 text-[12px] text-muted-foreground">
          <span>{{ t('problemSets.detail.progressTitle') }}</span>
          <span class="tabular-nums">{{ percent }}%</span>
        </div>
        <div class="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            class="h-full rounded-full bg-primary transition-[width] duration-300"
            :style="{ width: `${percent}%` }"
          />
        </div>
        <p class="pt-2 text-[12px] tabular-nums text-muted-foreground">
          {{ t('problemSets.detail.progressText', { done: solved, total }) }}
        </p>
      </div>
    </aside>
  </div>
</template>
