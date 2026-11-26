<script setup lang="ts">
/**
 * 团队详情 · 团队比赛面板：比赛卡片网格（搜索 / 分页 / 卡片点击进比赛详情）。
 * 管理角色带 ⋯ 行操作（编辑：仅未开始；赛时工具）；创建比赛走独立创建页。
 * 限界上下文：所有导航留在团队路由前缀内（frontend.md 路由上下文隔离）。
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { CirclePlus, MoreFilled } from '@element-plus/icons-vue'
import { NButton, NDropdown, NIcon, NSpin } from 'naive-ui'

import { listTeamContests } from '@/api/teams'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { formatCompact } from '@/utils/format'
import BaseAvatar from '@/components/BaseAvatar.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import type { ContestSummary } from '@/types'

const props = defineProps<{
  teamId: string
  isAdmin: boolean
}>()

const { t } = useI18n()
const router = useRouter()

const contests = ref<ContestSummary[]>([])
const contestsLoading = ref(false)
const contestKeyword = ref('')
const {
  page: contestPage,
  pageSize: contestPageSize,
  total: contestTotal,
  changePage: changeContestPage,
  resetPage: resetContestPage,
} = usePagination()

async function loadContests() {
  contestsLoading.value = true
  try {
    const result = await listTeamContests(props.teamId, {
      page: contestPage.value,
      page_size: contestPageSize.value,
      keyword: contestKeyword.value || undefined,
    })
    contests.value = result.items
    contestTotal.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    contestsLoading.value = false
  }
}

function searchContests() {
  resetContestPage()
  loadContests()
}

function openContest(row: ContestSummary) {
  // 限界上下文：留在团队路由前缀内（frontend.md 路由上下文隔离）
  void router.push(`/teams/${props.teamId}/contests/${row.id}`)
}

type ContestAction = 'manage' | 'tools'

function contestActions(row: ContestSummary): Array<{
  key: ContestAction
  label: string
  disabled?: boolean
}> {
  return [
    {
      key: 'manage',
      label: t('contests.detail.manage'),
      disabled: row.status !== 'scheduled',
    },
    { key: 'tools', label: t('contests.tools.title') },
  ]
}

function onContestAction(key: ContestAction, row: ContestSummary) {
  if (key === 'manage') {
    if (row.status !== 'scheduled') return
    void router.push(`/teams/${props.teamId}/contests/${row.id}/edit/basic`)
    return
  }
  void router.push(`/teams/${props.teamId}/contests/${row.id}/tools`)
}

/** 创建团队比赛 → 独立创建页（题目编排随后在比赛编辑页进行） */
function openContestCreate() {
  void router.push(`/teams/${props.teamId}/contests/new`)
}

const contestStatusLabel = computed(() => ({
  running: t('contests.statusRunning'),
  scheduled: t('contests.statusScheduled'),
  finished: t('contests.statusFinished'),
}))

onMounted(loadContests)
</script>

<template>
  <SearchFilterBar
    :keyword="contestKeyword"
    :placeholder="t('contests.list.search')"
    @update:keyword="
      (v: string) => {
        contestKeyword = v
      }
    "
    @search="searchContests"
    @reset="searchContests"
  >
    <template #actions>
      <NButton v-if="isAdmin" size="small" type="primary" @click="openContestCreate">
        <template #icon>
          <NIcon :component="CirclePlus" />
        </template>
        {{ t('teams.space.createContest') }}
      </NButton>
      <RefreshButton
        :loading="contestsLoading"
        :aria-label="t('action.refresh')"
        @click="loadContests"
      />
    </template>
  </SearchFilterBar>
  <PaginatedDataTable
    :data="contests"
    :loading="contestsLoading"
    :total="contestTotal"
    :page="contestPage"
    :page-size="contestPageSize"
    :empty-text="t('teams.space.contestsEmpty')"
    @update:page="
      (p: number) => {
        changeContestPage(p)
        loadContests()
      }
    "
  >
    <template #content>
      <div class="pane-scroll">
        <NSpin :show="contestsLoading" class="pane-spin">
          <ul v-if="contests.length" class="tile-grid tile-grid--contest">
            <li
              v-for="contest in contests"
              :key="contest.id"
              class="tile tile--contest tile--link"
              role="button"
              tabindex="0"
              @click="openContest(contest)"
              @keyup.enter="openContest(contest)"
            >
              <div class="tile__head">
                <BaseAvatar
                  kind="contest"
                  :src="contest.logo"
                  :name="contest.title"
                  :size="40"
                  :round="false"
                  :radius="8"
                  bordered
                />
                <h3 class="tile__title" :title="contest.title">{{ contest.title }}</h3>
                <span class="dot-chip" :class="`dot-chip--${contest.status}`">
                  <span class="dot-chip__dot" aria-hidden="true" />
                  {{ contestStatusLabel[contest.status] }}
                </span>
                <span
                  v-if="contest.board_frozen"
                  class="dot-chip dot-chip--frozen"
                  :title="t('contests.frozenHint')"
                >
                  <span class="dot-chip__dot" aria-hidden="true" />
                  {{ t('contests.boardFrozenTag') }}
                </span>
                <NDropdown
                  v-if="isAdmin"
                  class="tile__ops"
                  trigger="click"
                  :options="contestActions(contest)"
                  @select="(action: ContestAction) => onContestAction(action, contest)"
                >
                  <NButton
                    circle
                    quaternary
                    size="tiny"
                    :aria-label="t('teams.detail.more')"
                    @click.stop
                  >
                    <template #icon>
                      <NIcon :component="MoreFilled" />
                    </template>
                  </NButton>
                </NDropdown>
              </div>
              <p class="tile__desc" :class="{ 'tile__desc--empty': !contest.description }">
                {{ contest.description ?? '—' }}
              </p>
              <div class="tile__meta">
                <span class="tile__rule">{{ contest.rule_type }}</span>
                <span class="tile__sep" aria-hidden="true">·</span>
                <span>{{ t('contests.list.problemCount', { count: contest.problem_count }) }}</span>
                <span class="tile__sep" aria-hidden="true">·</span>
                <span>{{
                  t('contests.list.registeredCount', { count: contest.registered_count })
                }}</span>
              </div>
              <div class="tile__when">
                <span>{{ formatCompact(contest.start_time) }}</span>
                <span class="tile__when-arrow" aria-hidden="true">→</span>
                <span>{{ formatCompact(contest.end_time) }}</span>
              </div>
            </li>
          </ul>
        </NSpin>
      </div>
    </template>
  </PaginatedDataTable>
</template>

<style scoped>
/* pane 内滚动区：列表撑满，超出滚动 */
.pane-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: grid;
}
.pane-spin {
  min-height: 100%;
  display: flex;
  flex-direction: column;
}
.pane-spin :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* 比赛卡片：紧凑小卡片 */
.tile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
  list-style: none;
  margin: 0;
  padding: 0 0 4px;
  align-content: start;
}
.tile-grid--contest {
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.tile {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
  padding: 14px 16px;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  background: var(--app-card-bg, #fff);
  transition: border-color 0.15s ease;
}
.tile:hover {
  border-color: var(--app-text-muted);
}
.tile--link {
  cursor: pointer;
}
.tile--contest {
  flex-direction: column;
  align-items: stretch;
  gap: 12px;
  padding: 20px 20px 18px;
  /* 对齐公开比赛卡片范式：平面方角、纯 1px 边框，无彩条 / 着色底 / 动画 */
  border-radius: 0;
}
.tile--link:hover .tile__title {
  color: var(--app-primary);
}
.tile--link:focus-visible {
  outline: 2px solid var(--app-primary);
  outline-offset: 2px;
}
.tile__head {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.tile__title {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-size: 14px;
  font-weight: 650;
  line-height: 1.35;
  color: var(--app-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.15s ease;
}
.tile--contest .tile__title {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.4;
}
.tile__ops {
  flex-shrink: 0;
  margin: -2px -4px -2px 0;
}
.tile__desc {
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
.tile__desc--empty {
  opacity: 0.55;
}
.tile__meta {
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.35;
  font-variant-numeric: tabular-nums;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tile--contest .tile__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: visible;
  text-overflow: unset;
}
.tile__sep {
  opacity: 0.45;
}
.tile__rule {
  color: var(--app-primary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
}
.tile__when {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 6px;
  padding-top: 10px;
  border-top: 1px solid var(--app-border);
  color: var(--app-text-secondary);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.tile__when-arrow {
  opacity: 0.55;
}
.dot-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
  font-size: 11px;
  line-height: 1;
  color: var(--app-text-secondary);
}
.dot-chip__dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--app-text-muted);
}
/* 比赛状态点标与公开比赛卡片同范式：文本次级色，仅点着色（running 呼吸灯已随彩条样式移除） */
.dot-chip--running .dot-chip__dot {
  background: var(--app-success);
}
.dot-chip--scheduled .dot-chip__dot {
  background: var(--app-info);
}
.dot-chip--frozen {
  color: var(--app-warning);
}
.dot-chip--frozen .dot-chip__dot {
  background: var(--app-warning);
}
@media (hover: hover) {
  .tile__ops {
    opacity: 0;
    transition: opacity 0.15s ease;
  }
  .tile:hover .tile__ops,
  .tile:focus-within .tile__ops {
    opacity: 1;
  }
}

/* 响应式 */
@media (max-width: 860px) {
  .tile-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
