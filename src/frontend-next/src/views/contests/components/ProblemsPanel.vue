<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import ColumnLineList from '@/components/common/ColumnLineList.vue'
import InlineNotice from '@/components/common/InlineNotice.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { renderSolveMark } from '@/utils/solveMark'
import type { ContestDetail } from '@/types'

const props = defineProps<{ detail: ContestDetail }>()

const emit = defineEmits<{
  open: [problemId: string]
}>()

const { t } = useI18n()

const isIoi = computed(() => props.detail.rule_type === 'IOI')

function openProblem(row: { problem_id: string }): void {
  emit('open', row.problem_id)
}

const columns = computed<AppTableColumn<any>[]>(() => {
  const cols: AppTableColumn<any>[] = [
    {
      key: 'solved',
      title: '',
      width: '52px',
      cell: (row) => renderSolveMark(t, row.solved),
    },
    {
      key: 'letter',
      title: t('contests.detail.letter'),
      width: '64px',
      cell: (row) => String(row.letter ?? '--'),
      cellClass: 'text-[12.5px] font-medium tabular-nums text-muted-foreground',
    },
    {
      key: 'title',
      title: t('problems.list.name'),
      cell: (row) => String(row.title),
      cellClass: 'font-medium',
    },
  ]
  if (isIoi.value) {
    cols.push({
      key: 'score',
      title: t('contests.list.problemScore'),
      width: '90px',
      align: 'right',
      cell: (row) => (row.score > 0 ? String(row.score) : '--'),
      cellClass: 'text-[12.5px] tabular-nums text-muted-foreground',
    })
  }
  return cols
})
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-2">
    <InlineNotice v-if="!detail.can_view_problems">
      {{ t('contests.detail.notVisible') }}
    </InlineNotice>

    <ColumnLineList
      v-else
      :columns="columns"
      :items="detail.problems"
      :row-click="openProblem"
      :empty-text="t('contests.list.problemsEmpty')"
    />
  </div>
</template>
