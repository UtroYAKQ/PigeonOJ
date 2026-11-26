/**
 * 提交记录公共列：状态 / 分数 / 时间 / 内存 / 语言 + 提交类型标签。
 * 供管理全量列表与题目列表复用（H5：指标列工厂），行类型通用字段即可。
 */
import { h } from 'vue'
import { NTag } from 'naive-ui'
import type { DataTableColumn } from 'naive-ui'

import StatusTag from '@/components/StatusTag.vue'

type Translate = (key: string) => string

export interface SubmissionMetricsRow {
  status?: string
  score?: number | null
  time_used_ms?: number | null
  memory_used_kb?: number | null
  language?: string
}

/** 提交指标列：状态 / 分数 / 时间 / 内存 / 语言（各提交列表共用） */
export function submissionMetricColumns<T extends SubmissionMetricsRow>(
  t: Translate,
): DataTableColumn<T>[] {
  return [
    {
      title: t('problems.detail.status'),
      key: 'status',
      minWidth: 140,
      render: (row) => h(StatusTag, { status: row.status ?? '' }),
    },
    {
      title: t('problems.submission.score'),
      key: 'score',
      width: 80,
      render: (row) => row.score ?? '-',
    },
    {
      title: t('problems.submission.time'),
      key: 'time',
      width: 100,
      render: (row) => `${row.time_used_ms ?? '-'} ms`,
    },
    {
      title: t('problems.submission.memory'),
      key: 'memory',
      width: 110,
      render: (row) => `${row.memory_used_kb ?? '-'} KB`,
    },
    { title: t('problems.detail.language'), key: 'language', width: 110 },
  ]
}

/** 提交类型 → 标签元信息（practice / contest / verify） */
export const submitTypeMeta: Record<string, { labelKey: string; type: 'default' | 'info' | 'warning' }> = {
  practice: { labelKey: 'problems.submissionsManage.typePractice', type: 'default' },
  contest: { labelKey: 'problems.submissionsManage.typeContest', type: 'info' },
  verify: { labelKey: 'problems.submissionsManage.typeVerify', type: 'warning' },
}

/** 提交类型标签单元格（未知值回退原值） */
export function renderSubmitType<T extends { submit_type?: string }>(row: T, t: Translate) {
  const meta = submitTypeMeta[row.submit_type ?? '']
  if (!meta) return row.submit_type ?? '-'
  return h(NTag, { size: 'small', bordered: false, type: meta.type }, { default: () => t(meta.labelKey) })
}