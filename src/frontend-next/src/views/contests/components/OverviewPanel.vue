<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { CalendarClock, FileText } from '@lucide/vue'

import MarkdownView from '@/components/common/MarkdownView.vue'
import { Card } from '@/components/ui/card'
import ContestAnnouncement from './ContestAnnouncement.vue'
import { formatDateTime } from '@/utils/format'
import type { ContestDetail } from '@/types'

const props = defineProps<{ detail: ContestDetail }>()
const { t } = useI18n()

const schedule = computed(() => {
  const items = [
    { label: t('contests.list.startTime'), value: formatDateTime(props.detail.start_time) },
    { label: t('contests.list.endTime'), value: formatDateTime(props.detail.end_time) },
    {
      label: t('contests.list.regStartTime'),
      value: formatDateTime(props.detail.register_start_time),
    },
    { label: t('contests.list.regEndTime'), value: formatDateTime(props.detail.register_end_time) },
  ]
  if (props.detail.freeze_time) {
    items.push({
      label: t('contests.list.freezeAt'),
      value: formatDateTime(props.detail.freeze_time),
    })
  }
  return items
})
</script>

<template>
  <div class="space-y-3">
    <ContestAnnouncement
      v-if="detail.announcement"
      :source="detail.announcement"
      :updated-at="detail.announcement_updated_at"
    />

    <Card class="p-4">
      <h2 class="flex items-center gap-2 text-[13.5px] font-semibold">
        <CalendarClock class="size-4 text-muted-foreground" />
        {{ t('contests.detail.schedule') }}
      </h2>
      <dl
        class="mt-3 grid gap-3 sm:grid-cols-2"
        :class="schedule.length > 4 ? 'xl:grid-cols-5' : 'xl:grid-cols-4'"
      >
        <div v-for="item in schedule" :key="item.label" class="space-y-0.5">
          <dt class="text-[12px] text-muted-foreground">{{ item.label }}</dt>
          <dd class="text-[13px] font-medium tabular-nums">{{ item.value }}</dd>
        </div>
      </dl>
    </Card>

    <Card class="p-4">
      <h2 class="flex items-center gap-2 text-[13.5px] font-semibold">
        <FileText class="size-4 text-muted-foreground" />
        {{ t('contests.detail.about') }}
      </h2>
      <div class="mt-3">
        <MarkdownView v-if="detail.description" :source="detail.description" />
        <p v-else class="py-6 text-center text-[13px] text-muted-foreground">
          {{ t('contests.detail.noDescription') }}
        </p>
      </div>
    </Card>
  </div>
</template>
