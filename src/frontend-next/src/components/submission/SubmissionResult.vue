<script setup lang="ts">
import { computed, h, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import ColumnLineList from '@/components/common/ColumnLineList.vue'
import CodeBlockView from '@/components/common/CodeBlockView.vue'
import InlineNotice from '@/components/common/InlineNotice.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import { TONE_TEXT_CLASSES } from '@/components/common/tone'
import type { AppTableColumn } from '@/components/common/table-types'
import { Button } from '@/components/ui/button'
import type { Submission } from '@/types'

const props = defineProps<{
  submission: Submission
  pollingStopped?: boolean
}>()

const { t } = useI18n()
const showCode = ref(true)

const statusTone = computed(() => {
  const status = props.submission.status
  if (status === 'accepted') return TONE_TEXT_CLASSES.success
  if (status === 'pending' || status === 'judging') {
    return `${TONE_TEXT_CLASSES.default} animate-pulse`
  }
  return TONE_TEXT_CLASSES.danger
})

const statusLabel = computed(() => t(`problems.status.${props.submission.status}`))

const stats = computed(() => {
  const items: Array<{ label: string; value: string; unit?: string }> = []
  if (props.submission.score !== null) {
    items.push({ label: t('problems.submission.score'), value: String(props.submission.score) })
  }
  items.push({
    label: t('problems.submission.time'),
    value: String(props.submission.time_used_ms ?? 0),
    unit: 'ms',
  })
  items.push({
    label: t('problems.submission.memory'),
    value: String(props.submission.memory_used_kb ?? 0),
    unit: 'KB',
  })
  return items
})

const caseColumns = computed<AppTableColumn<any>[]>(() => [
  {
    key: 'case_name',
    title: '#',
    cell: (item) => h('span', { class: 'font-mono text-[12px]' }, item.case_name ?? '-'),
  },
  {
    key: 'status',
    title: t('problems.detail.status'),
    cell: (item) => h(StatusTag, { status: item.status }),
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
    key: 'score',
    title: t('problems.submission.score'),
    align: 'right',
    cell: (item) => String(item.score ?? '-'),
    cellClass: 'tabular-nums',
  },
])
</script>

<template>
  <div class="space-y-8">
    <section>
      <div class="flex flex-wrap items-center gap-2.5">
        <span class="text-xl font-semibold tracking-tight" :class="statusTone">
          {{ statusLabel }}
        </span>
        <ToneBadge v-if="submission.language" tone="info" :label="submission.language" />
        <ToneBadge
          v-if="submission.submit_type === 'verify'"
          tone="warning"
          :label="t('problems.submission.verifyType')"
        />
        <div v-if="$slots['status-actions']" class="ml-auto">
          <slot name="status-actions" />
        </div>
      </div>

      <div class="my-5 h-px bg-border" role="separator" />

      <div class="space-y-4">
        <InlineNotice v-if="pollingStopped" tone="info">
          {{ t('problems.submission.stillJudging') }}
        </InlineNotice>

        <div class="flex flex-wrap items-baseline gap-x-10 gap-y-4">
          <div v-for="stat in stats" :key="stat.label">
            <p class="text-[12px] font-medium text-muted-foreground">{{ stat.label }}</p>
            <p class="mt-1 text-[22px] font-semibold tabular-nums">
              {{ stat.value }}
              <span v-if="stat.unit" class="text-[12px] font-medium text-muted-foreground">{{
                stat.unit
              }}</span>
            </p>
          </div>
        </div>

        <InlineNotice v-if="submission.error_message" tone="danger">
          <p class="font-medium">{{ t('problems.submission.errorMessage') }}</p>
          <pre class="mt-1.5 whitespace-pre-wrap break-all font-mono text-[12px] leading-5">{{
            submission.error_message
          }}</pre>
        </InlineNotice>
      </div>
    </section>

    <section>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <h2 class="text-lg font-medium">{{ t('problems.submission.submittedCode') }}</h2>
        <Button variant="ghost" size="xs" @click="showCode = !showCode">
          {{ showCode ? t('problems.submission.hideCode') : t('problems.submission.showCode') }}
        </Button>
      </div>
      <div class="my-5 h-px bg-border" role="separator" />
      <CodeBlockView
        v-if="showCode"
        :code="submission.code ?? ''"
        :language="submission.language ?? ''"
        max-height="max-h-[420px]"
      />
    </section>

    <section v-if="submission.cases?.length">
      <h2 class="text-lg font-medium">{{ t('problems.submission.caseResults') }}</h2>
      <div class="my-5 h-px bg-border" role="separator" />
      <ColumnLineList
        :columns="caseColumns"
        :items="submission.cases"
        :empty-text="t('common.noData')"
      />
    </section>
  </div>
</template>
