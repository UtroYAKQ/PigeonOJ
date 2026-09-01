<script setup lang="ts">
/**
 * 题单详情（管理后台，admin/tutor）：题单元信息 + 题单内题目编排视图。
 * 「编排题目」按钮打开共享编排弹窗；编辑信息 / 下线同样收敛在本页。
 * 点击题目跳转前台题单上下文写题页（/problem-sets/:setId/problems/:problemId）。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import RefreshButton from '@/components/RefreshButton.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import ProblemSetArrangeModal from '@/components/problemsets/ProblemSetArrangeModal.vue'
import ProblemSetEditModal from '@/components/problemsets/ProblemSetEditModal.vue'
import { archiveProblemSet, getProblemSet } from '@/api/problemSets'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { ProblemSetDetail, ProblemSetItem, ProblemSetSummary } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const detail = ref<ProblemSetDetail | null>(null)

const editorShow = ref(false)
const arrangeShow = ref(false)

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

/** 共享弹窗消费的列表契约模型（编排弹窗按 id 拉详情） */
const asSummary = computed<ProblemSetSummary | null>(() => {
  if (!detail.value) return null
  const { items: _items, can_manage: _can_manage, ...summary } = detail.value
  return summary
})

const columns = computed<DataTableColumns<ProblemSetItem>>(() => [
  {
    title: t('problemSets.detail.orderLabel'),
    key: 'sort_order',
    width: 80,
    render: (row) => String(row.sort_order + 1),
  },
  {
    title: t('problemSets.detail.problems'),
    key: 'title',
    minWidth: 300,
    render: (row) => h('strong', null, row.title),
  },
  {
    title: t('problemSets.detail.difficulty'),
    key: 'difficulty',
    width: 100,
    render: (row) => (row.difficulty ?? null) === null ? '--' : String(row.difficulty),
  },
])

function goProblem(row: ProblemSetItem) {
  if (!detail.value) return
  // 题单管理内点击题目：只读预览（不进入写题页、不跳题库；契约约定）
  router.push(`/admin/problem-sets/${detail.value.id}/problems/${row.problem_id}/preview`)
}

function rowProps(row: ProblemSetItem) {
  return {
    style: 'cursor: pointer;',
    onClick: () => goProblem(row),
  }
}

function doArchive() {
  if (!detail.value) return
  confirmAsyncDialog({
    title: t('problemSets.detail.archive'),
    content: t('problemSets.detail.archiveConfirm'),
    positiveText: t('problemSets.detail.archive'),
    action: () => archiveProblemSet(detail.value!.id),
    successMessage: t('common.success'),
    onAfterSuccess: () => {
      router.push('/admin/problem-sets')
    },
  })
}
</script>

<template>
  <WorkbenchShell>
    <template #header>
      <div class="detail-head">
        <strong class="detail-head__title">{{ detail?.title ?? t('problemSets.detail.title') }}</strong>
        <n-tag v-if="detail?.status === 'archived'" type="warning" size="small">
          {{ t('problemSets.detail.archived') }}
        </n-tag>
      </div>
    </template>
    <template #header-extra>
      <div v-if="detail" class="detail-actions">
        <n-button type="primary" size="small" @click="arrangeShow = true">
          {{ t('problemSets.detail.arrange') }}
        </n-button>
        <n-button size="small" @click="editorShow = true">
          {{ t('problemSets.detail.edit') }}
        </n-button>
        <n-button
          v-if="detail.status === 'active'"
          size="small"
          type="error"
          secondary
          @click="doArchive"
        >
          {{ t('problemSets.detail.archive') }}
        </n-button>
      </div>
      <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
    </template>

    <n-spin :show="loading">
      <div v-if="detail" class="detail-body">
        <n-descriptions :column="3" size="small" label-placement="left" bordered>
          <n-descriptions-item :label="t('problemSets.list.visibility')">
            <n-tag size="small" :bordered="false" :type="detail.visibility === 'public' ? 'success' : 'default'">
              {{ t(detail.visibility === 'public'
                ? 'problemSets.list.visibilityPublic'
                : 'problemSets.list.visibilityPrivate') }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item :label="t('problemSets.list.status')">
            <n-tag size="small" :bordered="false" :type="detail.status === 'active' ? 'info' : 'warning'">
              {{ t(detail.status === 'active' ? 'problemSets.list.active' : 'problemSets.detail.archived') }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item :label="t('problemSets.detail.problems')">
            {{ t('problemSets.list.itemCount', { count: detail.item_count }) }}
          </n-descriptions-item>
          <n-descriptions-item :label="t('problemSets.list.descLabel')" :span="2">
            {{ detail.description || '--' }}
          </n-descriptions-item>
          <n-descriptions-item :label="t('problemSets.list.createdAt')">
            {{ formatDateTime(detail.created_at) }}
          </n-descriptions-item>
        </n-descriptions>

        <div class="detail-section__title">{{ t('problemSets.detail.problems') }}</div>
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

    <ProblemSetEditModal v-model:show="editorShow" :problem-set="asSummary" @saved="load" />
    <ProblemSetArrangeModal v-model:show="arrangeShow" :problem-set="asSummary" @saved="load" />
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
.detail-actions {
  display: inline-flex;
  gap: 8px;
  margin-right: 8px;
}
.detail-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 240px;
}
.detail-section__title {
  font-weight: 600;
  font-size: 14px;
}
.detail-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}
</style>
