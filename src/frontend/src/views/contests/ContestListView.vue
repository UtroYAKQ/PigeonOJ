<script setup lang="ts">
/**
 * 比赛中心（卡片流）：状态过滤 + 刷新；整卡点击进入比赛详情。
 * 卡片范式（与团队列表一致）：单行头部（头像 + 标题 + 右侧状态点标）、
 * 两行说明、赛制 / 题数 / 报名数元信息、底部时间窗；
 * 悬停仅边框加深 + 标题主色，无位移 / 阴影 / 动画。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import RefreshButton from '@/components/RefreshButton.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { listContests } from '@/api/contests'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { formatDateTime } from '@/utils/format'
import type { ContestSummary, PageResult } from '@/types'

const router = useRouter()
const { t } = useI18n()
const loading = ref(false)
const rows = ref<ContestSummary[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()
const keyword = ref('')
const statusFilter = ref<'running' | 'scheduled' | 'finished' | null>(null)

async function load() {
  const seq = beginLoad()
  loading.value = true
  try {
    const result: PageResult<ContestSummary> = await listContests({
      page: page.value,
      page_size: pageSize.value,
      status: statusFilter.value ?? undefined,
      keyword: keyword.value || undefined,
    })
    if (!isCurrent(seq)) return
    rows.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

function onSearch() {
  resetPage()
  load()
}

onMounted(load)

const statusOptions = computed(() => [
  { label: t('common.allStatus'), value: 'all' },
  { label: t('contests.statusRunning'), value: 'running' },
  { label: t('contests.statusScheduled'), value: 'scheduled' },
  { label: t('contests.statusFinished'), value: 'finished' },
])
const statusValue = computed({
  get: () => statusFilter.value ?? 'all',
  set: (v: string) => {
    statusFilter.value = v === 'all' ? null : (v as 'running' | 'scheduled' | 'finished')
    load()
  },
})

const statusLabel = computed<Record<string, string>>(() => ({
  running: t('contests.statusRunning'),
  scheduled: t('contests.statusScheduled'),
  finished: t('contests.statusFinished'),
}))

function initialOf(row: ContestSummary): string {
  return (row.title || '?').trim().charAt(0).toUpperCase()
}

function openContest(row: ContestSummary) {
  router.push(`/contests/${row.id}`)
}
</script>

<template>
  <WorkbenchShell>
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('contests.list.search')"
      search-width="300px"
      @update:keyword="
        (v: string) => {
          keyword = v
        }
      "
      @search="onSearch"
      @reset="onSearch"
    >
      <n-select
        v-model:value="statusValue"
        style="width: 132px"
        :options="statusOptions"
        :aria-label="t('contests.statusRunning')"
      />
      <template #actions>
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <!-- 与题库 / 题单（PaginatedDataTable）同构：spin 只渲染卡片墙（全局类 table-fill 吃满），
         空态为其兄弟节点、用全局类 table-fill-empty 拉伸居中；
         v-show 而非 v-if（分支锚点增删会触发 Vue patch 崩溃，同 PaginatedDataTable 注释） -->
    <n-spin
      v-show="loading || rows.length"
      :show="loading"
      class="table-fill"
      content-style="height: 100%; overflow: auto"
    >
      <div class="cards">
        <article
          v-for="row in rows"
          :key="row.id"
          class="contest-card"
          role="button"
          tabindex="0"
          @click="openContest(row)"
          @keyup.enter="openContest(row)"
        >
          <div class="contest-card__top">
            <img v-if="row.logo" :src="row.logo" alt="" class="contest-card__logo" />
            <div
              v-else
              class="contest-card__logo contest-card__logo--fallback"
              aria-hidden="true"
            >
              {{ initialOf(row) }}
            </div>
            <h3 class="contest-card__title" :title="row.title">{{ row.title }}</h3>
            <span class="state-chip" :class="`state-chip--${row.status}`">
              <span class="state-chip__dot" aria-hidden="true" />
              {{ statusLabel[row.status] }}
            </span>
            <span
              v-if="row.board_frozen"
              class="state-chip state-chip--frozen"
              :title="t('contests.frozenHint')"
            >
              <span class="state-chip__dot" aria-hidden="true" />
              {{ t('contests.boardFrozenTag') }}
            </span>
          </div>

          <p class="contest-card__desc" :class="{ 'contest-card__desc--empty': !row.description }">
            {{ row.description ?? '—' }}
          </p>

          <div class="contest-card__meta">
            <span class="contest-card__rule">{{ row.rule_type }}</span>
            <span class="contest-card__sep" aria-hidden="true">·</span>
            <span>{{ t('contests.list.problemCount', { count: row.problem_count }) }}</span>
            <span class="contest-card__sep" aria-hidden="true">·</span>
            <span>{{ t('contests.list.registeredCount', { count: row.registered_count }) }}</span>
          </div>

          <div class="contest-card__footer">
            <span>{{ formatDateTime(row.start_time) }}</span>
            <span class="contest-card__range" aria-hidden="true">→</span>
            <span>{{ formatDateTime(row.end_time) }}</span>
          </div>
        </article>
      </div>
    </n-spin>
    <div v-show="!loading && !rows.length" class="table-fill-empty">
      <n-empty size="large" :description="t('contests.list.empty')" />
    </div>

    <div v-if="total > 0" class="pager">
      <span class="pager__total">{{ t('contests.list.totalCount', { count: total }) }}</span>
      <div class="pager__spacer" />
      <n-pagination
        :page="page"
        :page-size="pageSize"
        :item-count="total"
        :page-sizes="[12, 24, 48]"
        show-size-picker
        @update:page="
          (p: number) => {
            changePage(p)
            load()
          }
        "
        @update:page-size="
          (s: number) => {
            changeSize(s)
            load()
          }
        "
      />
    </div>
  </WorkbenchShell>
</template>

<style scoped>
/* 空态与高度链由全局类 table-fill / table-fill-empty 承载（main.css），
   与题库 / 题单列表同一机制 */
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  min-height: 240px;
  align-content: start;
}

/* ---- 卡片：单行头部（头像 + 标题 + 右侧状态点标），纯平面极简 ---- */
.contest-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px 20px 18px;
  border: 1px solid var(--app-border);
  background: var(--app-card-bg, #fff);
  cursor: pointer;
  transition: border-color 0.15s ease;
}
.contest-card:hover {
  border-color: var(--app-text-muted);
}
.contest-card:hover .contest-card__title {
  color: var(--app-primary);
}
.contest-card:focus-visible {
  outline: 2px solid var(--app-primary);
  outline-offset: 2px;
}
.contest-card__top {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.contest-card__logo {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid var(--app-border);
  flex-shrink: 0;
}
.contest-card__logo--fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--app-muted-bg);
  border: 1px solid var(--app-border);
  color: var(--app-text-secondary);
  font-size: 16px;
  font-weight: 650;
}
.contest-card__title {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--app-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.15s ease;
}
/* 状态 = 色点 + 文本（不单一靠颜色，文本承载语义） */
.state-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
  font-size: 11px;
  line-height: 1;
  color: var(--app-text-secondary);
}
.state-chip__dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--app-text-muted);
}
.state-chip--running .state-chip__dot {
  background: var(--app-success);
}
.state-chip--scheduled .state-chip__dot {
  background: var(--app-info);
}
.state-chip--finished .state-chip__dot {
  background: var(--app-text-muted);
}
.state-chip--frozen {
  color: var(--app-warning);
}
.state-chip--frozen .state-chip__dot {
  background: var(--app-warning);
}
/* 描述固定两行高度：无描述也占位，保证同排卡片底部对齐 */
.contest-card__desc {
  margin: 0;
  min-height: 37px;
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.contest-card__desc--empty {
  opacity: 0.55;
}
.contest-card__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.contest-card__rule {
  color: var(--app-primary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
}
.contest-card__sep {
  opacity: 0.45;
}
.contest-card__footer {
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px solid var(--app-border);
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--app-text-secondary);
  font-variant-numeric: tabular-nums;
}
.contest-card__range {
  opacity: 0.55;
}
.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 18px;
  padding-top: 12px;
  border-top: 1px solid var(--app-border);
}
.pager__spacer {
  flex: 1;
}
</style>
