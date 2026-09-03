<script setup lang="ts">
/**
 * 题单详情 / 刷题页（浏览）：题目按 sort_order 展示（刷题不强制按序完成）。
 * 点击题目进入题单上下文写题页（/problem-sets/:setId/problems/:problemId，
 * 复用题库详情组件；交题与评测结果均在题单路由内完成，不跳转题库）。
 * 管理操作（编辑信息 / 编排题目 / 下线）统一在管理后台 /admin/problem-sets。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { DataTableColumns } from 'naive-ui'

import RefreshButton from '@/components/RefreshButton.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { getProblemSet } from '@/api/problemSets'
import { message } from '@/utils/feedback'
import { renderSolveMark } from '@/utils/solveMark'
import type { ProblemSetDetail, ProblemSetItem } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const detail = ref<ProblemSetDetail | null>(null)

async function load() {
  loading.value = true
  try {
    detail.value = await getProblemSet(String(route.params.id))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}
onMounted(load)

const columns = computed<DataTableColumns<ProblemSetItem>>(() => [
  {
    title: t('problemSets.detail.orderLabel'),
    key: 'sort_order',
    width: 80,
    render: (row) => String(row.sort_order + 1),
  },
  {
    title: '',
    key: 'solved',
    width: 72,
    render: (row) => renderSolveMark(t, row.solved),
  },
  {
    title: t('problemSets.detail.problems'),
    key: 'title',
    minWidth: 300,
    render: (row) => h('strong', null, row.title),
  },
  {
    title: t('problems.list.limits'),
    key: 'limits',
    width: 220,
    render: (row) => `${row.time_limit_ms ?? '--'} ms / ${row.memory_limit_mb ?? '--'} MB`,
  },
  {
    title: t('problemSets.detail.difficulty'),
    key: 'difficulty',
    width: 100,
    render: (row) => ((row.difficulty ?? null) === null ? '--' : String(row.difficulty)),
  },
])

function goProblem(row: ProblemSetItem) {
  if (!detail.value) return
  router.push(`/problem-sets/${detail.value.id}/problems/${row.problem_id}`)
}

function rowProps(row: ProblemSetItem) {
  return {
    style: 'cursor: pointer;',
    onClick: () => goProblem(row),
  }
}
</script>

<template>
  <WorkbenchShell>
    <template #header>
      <div class="detail-head">
        <strong class="detail-head__title">{{
          detail?.title ?? t('problemSets.detail.title')
        }}</strong>
        <n-tag v-if="detail?.status === 'archived'" type="warning" size="small">
          {{ t('problemSets.detail.archived') }}
        </n-tag>
      </div>
    </template>
    <template #header-extra>
      <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
    </template>

    <n-spin :show="loading">
      <div v-if="detail" class="detail-body">
        <n-data-table
          v-if="detail.items.length"
          :columns="columns"
          :data="detail.items"
          :loading="loading"
          :bordered="false"
          :bottom-bordered="false"
          :row-props="rowProps"
        />
        <div v-else class="detail-empty">
          <n-empty size="large" :description="t('problemSets.detail.empty')" />
        </div>
      </div>
    </n-spin>
  </WorkbenchShell>
</template>

<style scoped>
.detail-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.detail-head__title {
  font-size: 16px;
}
.detail-body {
  min-height: 240px;
}
.detail-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 240px;
}
</style>
