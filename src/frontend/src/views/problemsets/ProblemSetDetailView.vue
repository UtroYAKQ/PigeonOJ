<script setup lang="ts">
/**
 * 题单详情 / 刷题页（前台浏览）：标题区 + tabs（信息 / 题目列表）。
 * 布局约定：固定部分（标题 / tab 导航）自然排列，tab 内容区显式定高
 * （calc(100dvh - 300px)，与 AdminConfigsView 表格同款口径）填满剩余视口；
 * 滚动只发生在 info-main / problems-scroll 内部，页面级不出滚动条。
 * 「信息」tab 左 7 右 3：左 Markdown 介绍，右创建人 / 创建时间 / 完成进度。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import MarkdownView from '@/components/MarkdownView.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { getProblemSet } from '@/api/problemSets'
import { message } from '@/utils/feedback'
import { renderSolveMark } from '@/utils/solveMark'
import { formatDateTime } from '@/utils/format'
import type { ProblemSetDetail, ProblemSetItem } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const detail = ref<ProblemSetDetail | null>(null)
const activeTab = ref<'info' | 'problems'>('info')

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

/** 完成进度：当前用户 AC 题数 / 题单题数（匿名=0） */
const solvedCount = computed(
  () => (detail.value?.items ?? []).filter((it) => it.solved === true).length,
)
const totalCount = computed(() => detail.value?.items.length ?? 0)
const progressPercent = computed(() =>
  totalCount.value ? Math.round((solvedCount.value / totalCount.value) * 100) : 0,
)

const columns = computed<DataTableColumns<ProblemSetItem>>(() => [
  {
    title: t('problemSets.detail.orderLabel'),
    key: 'order',
    width: 64,
    render: (_row, index) => h('span', { class: 'item-order' }, String(index + 1)),
  },
  {
    title: '',
    key: 'solved',
    width: 56,
    render: (row) => renderSolveMark(t, row.solved),
  },
  {
    title: t('problemSets.list.titleLabel'),
    key: 'title',
    minWidth: 260,
    render: (row) => h('strong', null, row.title),
  },
  {
    title: t('problems.list.limits'),
    key: 'limits',
    width: 180,
    render: (row) => `${row.time_limit_ms ?? '--'} ms / ${row.memory_limit_mb ?? '--'} MB`,
  },
  {
    title: t('problemSets.detail.difficulty'),
    key: 'difficulty',
    width: 90,
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

function rowKey(row: ProblemSetItem) {
  return row.problem_id
}
</script>

<template>
  <WorkbenchShell>
    <n-spin :show="loading">
      <div v-if="detail" class="detail-wrap">
        <!-- 标题区：纯排版（标题 + 标签 + 元信息一行） -->
        <section class="hero">
          <div class="hero__title-row">
            <h2 class="hero__title">{{ detail.title }}</h2>
            <n-tag
              size="small"
              :bordered="false"
              :type="detail.visibility === 'public' ? 'info' : 'error'"
            >
              {{
                t(
                  detail.visibility === 'public'
                    ? 'problemSets.list.visibilityPublic'
                    : 'problemSets.list.visibilityPrivate',
                )
              }}
            </n-tag>
            <n-tag v-if="detail.status === 'archived'" type="warning" size="small">
              {{ t('problemSets.detail.archived') }}
            </n-tag>
          </div>
          <div class="hero__meta-row">
            <p class="hero__meta">
              {{ t('problemSets.detail.ownerLabel', { name: detail.owner_name || '--' }) }}
              <span class="hero__dot">·</span>
              {{ formatDateTime(detail.created_at) }}
            </p>
            <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
          </div>
        </section>

        <!-- tabs：信息 / 题目列表 -->
        <n-tabs v-model:value="activeTab" type="line" class="detail-tabs">
          <!-- 信息 tab：左 7 右 3 -->
          <n-tab-pane name="info" :tab="t('problemSets.detail.tabInfo')">
            <div class="pane-fill info-grid">
              <div class="info-main">
                <MarkdownView
                  v-if="detail.description"
                  :source="detail.description"
                  class="info-main__desc"
                />
                <n-empty
                  v-else
                  size="small"
                  :description="t('problemSets.detail.noDescription')"
                  class="info-main__empty"
                />
              </div>

              <aside class="info-aside">
                <div class="side-row">
                  <span class="side-row__label">{{ t('problemSets.detail.ownerLabelPlain') }}</span>
                  <span class="side-row__value">{{ detail.owner_name || '--' }}</span>
                </div>
                <div class="side-row">
                  <span class="side-row__label">{{ t('problemSets.list.createdAt') }}</span>
                  <span class="side-row__value">{{ formatDateTime(detail.created_at) }}</span>
                </div>
                <div class="side-progress">
                  <n-progress
                    type="line"
                    :percentage="progressPercent"
                    :show-indicator="false"
                    class="side-progress__bar"
                  />
                  <span class="side-progress__text">
                    {{
                      t('problemSets.detail.progressText', {
                        done: solvedCount,
                        total: totalCount,
                      })
                    }}
                  </span>
                </div>
              </aside>
            </div>
          </n-tab-pane>

          <!-- 题目列表 tab -->
          <n-tab-pane name="problems" :tab="t('problemSets.detail.problems')">
            <div class="pane-fill problems-scroll">
              <n-data-table
                size="medium"
                :columns="columns"
                :data="detail.items"
                :bordered="false"
                :bottom-bordered="false"
                :row-props="rowProps"
                :row-key="rowKey"
              />
              <n-empty
                v-if="!detail.items.length"
                size="large"
                :description="t('problemSets.detail.empty')"
                class="problems-empty"
              />
            </div>
          </n-tab-pane>
        </n-tabs>
      </div>
    </n-spin>
  </WorkbenchShell>
</template>

<style scoped>
/* 布局思路：固定部分自然排列；tab 内容区显式定高（项目通用口径 calc(100dvh - 300px)，
   预算：顶栏 60 + 页面内边距 28 + 卡片内边距 ~40 + 标题区 ~90 + tab 导航 ~52 + 余量 ~30）。
   不依赖 n-spin / n-tabs 内部结构传 flex 高度，滚动全部收敛在 pane 内部。 */
.detail-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* 标题区 */
.hero {
  padding: 4px 4px 0;
}
.hero__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.hero__title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  line-height: 1.3;
}
.hero__meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 6px;
}
.hero__meta {
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 13px;
}
.hero__dot {
  margin: 0 4px;
}

/* tab 内容区：定高填满剩余视口，两个 tab 共用 */
.pane-fill {
  height: calc(100dvh - 260px);
  min-height: 320px;
}

/* 信息 tab：左 7 右 3 */
.info-grid {
  display: grid;
  grid-template-columns: minmax(0, 7fr) minmax(0, 3fr);
  grid-template-rows: minmax(0, 1fr);
  gap: 32px;
}
.info-main {
  overflow: auto;
  min-height: 0;
  padding-right: 8px;
}
.info-main__empty {
  padding: 48px 0;
}
.info-aside {
  overflow: auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding-left: 24px;
  border-left: 1px solid var(--app-border);
}
.side-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  font-size: 13px;
}
.side-row + .side-row {
  border-top: 1px dashed var(--app-border);
}
.side-row__label {
  color: var(--app-text-secondary);
  flex-shrink: 0;
}
.side-row__value {
  text-align: right;
}
.side-progress {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px dashed var(--app-border);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.side-progress__text {
  font-size: 13px;
  color: var(--app-text-secondary);
}

/* 题目列表 tab：表格内部滚动 */
.problems-scroll {
  overflow: auto;
}
.problems-empty {
  padding: 40px 0;
}
.item-order {
  color: var(--app-text-secondary);
  font-size: 12px;
}
@media (max-width: 960px) {
  /* 窄屏退回文档流：页面自然滚动，各区域自适应高度 */
  .pane-fill {
    height: auto;
    min-height: 0;
  }
  .info-grid {
    grid-template-columns: 1fr;
    grid-template-rows: none;
    gap: 20px;
  }
  .info-main,
  .info-aside,
  .problems-scroll {
    overflow: visible;
  }
  .info-aside {
    border-left: none;
    padding-left: 0;
    border-top: 1px solid var(--app-border);
    padding-top: 8px;
  }
}
</style>
