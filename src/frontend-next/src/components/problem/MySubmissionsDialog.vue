<script setup lang="ts">
import { computed, h, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { listSubmissions } from '@/api/judge'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { usePagination } from '@/composables/usePagination'
import { formatDateTime } from '@/utils/format'
import type { Submission } from '@/types'

const props = defineProps<{ problemId: string; submissionsBase: string }>()
const open = defineModel<boolean>('open', { required: true })

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const list = ref<Submission[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination({ defaultPageSize: 10 })

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listSubmissions({
      problem_id: props.problemId,
      page: page.value,
      page_size: pageSize.value,
    })
    if (!isCurrent(seq)) return
    list.value = result.items
    total.value = result.total
  } catch {
    /* 未登录等场景静默 */
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

watch(open, (value) => {
  if (!value) return
  resetPage()
  void load()
})

function openSubmission(row: Submission): void {
  open.value = false
  router.push(`${props.submissionsBase}/submissions/${row.id}`)
}

const columns = computed<AppTableColumn<Submission>[]>(() => [
  {
    key: 'status',
    title: t('problems.detail.status'),
    width: '150px',
    cell: (row) => h(StatusTag, { status: row.status }),
  },
  {
    key: 'score',
    title: t('problems.submission.score'),
    width: '80px',
    align: 'right',
    cell: (row) => row.score ?? '-',
  },
  {
    key: 'time',
    title: t('problems.submission.time'),
    width: '110px',
    align: 'right',
    cell: (row) => `${row.time_used_ms ?? '-'} ms`,
  },
  { key: 'language', title: t('problems.detail.language'), width: '120px' },
  {
    key: 'created_at',
    title: t('problems.submissionsManage.submitTime'),
    cell: (row) => (row.created_at ? formatDateTime(row.created_at) : '-'),
  },
])

defineExpose({ load, reset: resetPage })
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent
      class="flex h-[min(72vh,520px)] flex-col gap-0 overflow-hidden p-0 sm:max-w-[760px]"
    >
      <div class="border-b border-border px-5 py-4 pr-12">
        <DialogTitle class="text-[15px] font-semibold">
          {{ t('problems.detail.mySubmissions') }}
        </DialogTitle>
        <DialogDescription class="sr-only">
          {{ t('problems.detail.mySubmissions') }}
        </DialogDescription>
      </div>

      <div class="min-h-0 flex-1 p-4">
        <PaginatedTable
          :columns="columns"
          :data="list"
          :loading="loading"
          :total="total"
          :page="page"
          :page-size="pageSize"
          :empty-text="t('problems.detail.noSubmissions')"
          :row-click="openSubmission"
          class="h-full"
          @update:page="
            (value: number) => {
              changePage(value)
              load()
            }
          "
          @update:page-size="
            (value: number) => {
              changeSize(value)
              load()
            }
          "
        />
      </div>

      <div class="flex justify-end border-t border-border px-4 py-2.5">
        <Button variant="outline" size="sm" @click="open = false">
          {{ t('action.close') }}
        </Button>
      </div>
    </DialogContent>
  </Dialog>
</template>
