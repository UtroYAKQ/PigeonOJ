<script setup lang="ts">
import { computed, h } from 'vue'
import { useI18n } from 'vue-i18n'

import ColumnLineList from '@/components/common/ColumnLineList.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { formatDateTime } from '@/utils/format'
import type { ContestSubmissionItem } from '@/types'

const props = defineProps<{
  open: boolean
  loading: boolean
  title: string
  items: ContestSubmissionItem[]
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  openSubmission: [item: ContestSubmissionItem]
}>()

const { t } = useI18n()

const columns = computed<AppTableColumn<ContestSubmissionItem>[]>(() => [
  {
    key: 'status',
    title: t('problems.detail.status'),
    cell: (item) => h(StatusTag, { status: item.status }),
  },
  {
    key: 'score',
    title: t('problems.submission.score'),
    align: 'right',
    cell: (item) => String(item.score ?? '-'),
    cellClass: 'tabular-nums',
  },
  {
    key: 'time_used_ms',
    title: t('problems.submission.time'),
    align: 'right',
    cell: (item) => `${item.time_used_ms ?? '-'} ms`,
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'memory_used_kb',
    title: t('problems.submission.memory'),
    align: 'right',
    cell: (item) => `${item.memory_used_kb ?? '-'} KB`,
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'language',
    title: t('problems.detail.language'),
    cell: (item) => item.language,
    cellClass: 'text-[12.5px]',
  },
  {
    key: 'created_at',
    title: t('contests.submissions.submitTime'),
    cell: (item) => formatDateTime(item.created_at),
    cellClass: 'tabular-nums text-muted-foreground',
  },
])

function onOpenChange(value: boolean): void {
  emit('update:open', value)
}
</script>

<template>
  <Dialog :open="open" @update:open="onOpenChange">
    <DialogContent class="sm:max-w-3xl">
      <DialogHeader>
        <DialogTitle>{{ title }} · {{ t('contests.board.successfulSubmissions') }}</DialogTitle>
        <DialogDescription class="sr-only">
          {{ t('contests.board.successfulSubmissions') }}
        </DialogDescription>
      </DialogHeader>

      <ColumnLineList
        class="max-h-[420px]"
        :columns="columns"
        :items="props.items"
        :loading="loading"
        :row-click="(item) => emit('openSubmission', item)"
        :empty-text="t('contests.board.emptyCellSubmissions')"
      />
    </DialogContent>
  </Dialog>
</template>
