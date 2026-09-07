<script setup lang="ts">
/**
 * 题单详情 / 刷题页（前台浏览）：标题区 + tabs（信息 / 题目列表）。
 * 布局约定：固定部分（标题 / tab 导航）自然排列，tab 内容区显式定高
 * （calc(100dvh - 300px)，与 AdminConfigsView 表格同款口径）填满剩余视口；
 * 滚动只发生在 info-main / problems-scroll 内部，页面级不出滚动条。
 * 「信息」tab 左 7 右 3：左 Markdown 介绍，右创建人 / 创建时间 / 完成进度。
 */
import { computed, h, onActivated, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import MarkdownView from '@/components/MarkdownView.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { getProblemSet } from '@/api/problemSets'
import { getTeamProblemSet } from '@/api/teams'
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

/** 上下文取参（frontend.md 路由上下文隔离）：团队上下文读团队端点，否则题单统一入口 */
const teamId = computed(() => (route.params.teamId ? String(route.params.teamId) : null))
const setId = computed(() =>
  route.params.setId ? String(route.params.setId) : String(route.params.id),
)

async function load() {
  loading.value = true
  try {
    detail.value = await (teamId.value
      ? getTeamProblemSet(teamId.value, setId.value)
      : getProblemSet(setId.value))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}
onMounted(load)
// keepAlive 页面：从编排页返回时命中缓存实例（onMounted 不再执行），
// onActivated 强制重拉，保证题单内容与服务器一致（frontend.md 数据时效约定）
onActivated(() => {
  if (detail.value) void load()
})

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
  const target = teamId.value
    ? `/teams/${teamId.value}/sets/${detail.value.id}/problems/${row.problem_id}`
    : `/problem-sets/${detail.value.id}/problems/${row.problem_id}`
  router.push(target)
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
                  class="table-fill-empty info-main__empty"
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

          <!-- 题目列表 tab：空态样板（frontend.md）——表格 v-show 隐藏（避免与空态双重渲染），
               空态用全局 table-fill-empty 在固定高 pane 内拉伸居中 -->
          <n-tab-pane name="problems" :tab="t('problemSets.detail.problems')">
            <div class="pane-fill problems-scroll">
              <n-data-table
                v-show="detail.items.length"
                size="medium"
                :columns="columns"
                :data="detail.items"
                :bordered="false"
                :bottom-bordered="false"
                :row-props="rowProps"
                :row-key="rowKey"
              />
              <n-empty v-show="!detail.items.length" size="large" :description="t('problemSets.detail.empty')" />
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
  display: flex;
  flex-direction: column;
}
/* 空态拉伸居中（全局 table-fill-empty）；格子有界，去掉 320px 下限 */
.info-main__empty {
  min-height: 0;
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

/* 题目列表 tab：表格内部滚动；空态 flex 拉伸居中 */
.problems-scroll {
  overflow: auto;
  display: flex;
  flex-direction: column;
}
.problems-empty {
  min-height: 0;
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
