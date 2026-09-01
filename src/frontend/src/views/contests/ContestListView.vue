<script setup lang="ts">
/**
 * 比赛中心（卡片流）：状态过滤 + 刷新；整卡点击进入比赛详情。
 * 卡片布局：左上比赛头像（无头像回退渐变底 + 首字）、右上状态与封榜徽标、
 * 下方比赛名称、两行说明、赛制 / 题数 / 报名数元信息、底部时间窗。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NTag } from 'naive-ui'

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

const statusMeta = computed(() => ({
  running: { label: t('contests.statusRunning'), type: 'success' as const },
  scheduled: { label: t('contests.statusScheduled'), type: 'info' as const },
  finished: { label: t('contests.statusFinished'), type: 'default' as const },
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
      manual
      @update:keyword="(v: string) => { keyword = v }"
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

    <n-spin :show="loading" class="cards-fill">
      <div v-if="rows.length" class="cards">
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
            <img v-if="row.logo" :src="row.logo" alt="logo" class="contest-card__logo" />
            <div v-else class="contest-card__logo contest-card__logo--fallback">
              {{ initialOf(row) }}
            </div>
            <div class="contest-card__badges">
              <NTag
                size="small"
                round
                :bordered="false"
                :type="statusMeta[row.status].type"
              >
                {{ statusMeta[row.status].label }}
              </NTag>
              <NTag
                v-if="row.board_frozen"
                size="small"
                round
                type="warning"
                :bordered="false"
              >
                {{ t('contests.boardFrozenTag') }}
              </NTag>
            </div>
          </div>

          <h3 class="contest-card__title" :title="row.title">{{ row.title }}</h3>
          <p v-if="row.description" class="contest-card__desc">{{ row.description }}</p>

          <div class="contest-card__meta">
            <span class="contest-card__rule">{{ row.rule_type }}</span>
            <span class="contest-card__dot" aria-hidden="true">·</span>
            <span>{{ t('contests.list.problemCount', { count: row.problem_count }) }}</span>
            <span class="contest-card__dot" aria-hidden="true">·</span>
            <span>{{ t('contests.list.registeredCount', { count: row.registered_count }) }}</span>
          </div>

          <div class="contest-card__footer">
            <span>{{ formatDateTime(row.start_time) }}</span>
            <span class="contest-card__arrow" aria-hidden="true">→</span>
            <span>{{ formatDateTime(row.end_time) }}</span>
          </div>
        </article>
      </div>
      <div v-else-if="!loading" class="cards-empty">
        <n-empty size="large" :description="t('contests.list.empty')" />
      </div>
    </n-spin>

    <div v-if="total > 0" class="pager">
      <span class="pager__total">{{ t('contests.list.totalCount', { count: total }) }}</span>
      <div class="pager__spacer" />
      <n-pagination
        :page="page"
        :page-size="pageSize"
        :item-count="total"
        :page-sizes="[12, 24, 48]"
        show-size-picker
        @update:page="(p: number) => { changePage(p); load() }"
        @update:page-size="(s: number) => { changeSize(s); load() }"
      />
    </div>
  </WorkbenchShell>
</template>

<style scoped>
/* 视口锁定高度链：page-fill 的直接子元素需吃满剩余高度，分页器才能钉底 */
.cards-fill {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.cards-fill :deep(.n-spin-container),
.cards-fill :deep(.n-spin-content) {
  height: 100%;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 18px;
  min-height: 240px;
}
.cards-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
}

/* ---- 卡片：头像左上 / 徽标右上 / 名称其下 / 元信息与时间窗收尾 ---- */
.contest-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: var(--app-card-bg, #fff);
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease;
}
.contest-card:hover {
  border-color: var(--app-primary);
  box-shadow: 0 4px 14px rgb(0 0 0 / 6%);
}
.contest-card:focus-visible {
  outline: 2px solid var(--app-primary);
  outline-offset: 2px;
}
.contest-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.contest-card__logo {
  width: 52px;
  height: 52px;
  border-radius: 10px;
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
  font-size: 20px;
  font-weight: 700;
}
.contest-card__badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}
.contest-card__title {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
  line-height: 1.35;
  color: var(--app-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.contest-card__desc {
  margin: -4px 0 0;
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
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
  font-weight: 700;
  letter-spacing: 0.5px;
}
.contest-card__dot {
  opacity: 0.5;
}
.contest-card__footer {
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px dashed var(--app-border);
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--app-text-secondary);
  font-variant-numeric: tabular-nums;
}
.contest-card__arrow {
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
