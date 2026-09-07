<script setup lang="ts">
/**
 * 团队详情（管理后台，admin；docs/contracts/teams.md 管理端）：
 * 顶部团队信息卡（头像 / 名称 / 状态 / 创建人 / 成员数 / 资源统计）+
 * 模块 tab（成员 / 团队题库 / 团队题单 / 团队比赛），全部走 /admin/teams*
 * 管理端只读视图（免团队角色；含已解散团队与草稿 / 归档 / 已下线资源）。
 * 管理端不做团队内容维护——维护动作收敛在团队空间（/teams/:id，创建者 / 团队管理员）。
 */
import { computed, h, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NAvatar, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import {
  adminGetTeam,
  adminListTeamContests,
  adminListTeamMembers,
  adminListTeamProblemSets,
  adminListTeamProblems,
} from '@/api/admin'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { formatDateTime } from '@/utils/format'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import type {
  ContestSummary,
  ProblemSetSummary,
  TeamAdminDetail,
  TeamMemberItem,
  TeamProblemSummary,
} from '@/types'

type TeamModule = 'members' | 'problems' | 'sets' | 'contests'

const route = useRoute()
const { t } = useI18n()

const teamId = String(route.params.id)
const loading = ref(false)
const detail = ref<TeamAdminDetail | null>(null)
const loadFailed = ref(false)

function initialOf(name: string | null | undefined) {
  return name?.trim()?.charAt(0).toUpperCase() || 'T'
}

async function load() {
  loading.value = true
  try {
    detail.value = await adminGetTeam(teamId)
    loadFailed.value = false
  } catch (error) {
    loadFailed.value = true
    message.error(error instanceof Error ? error.message : t('admin.teams.loadFailed'))
  } finally {
    loading.value = false
  }
}
onMounted(load)

const isActive = computed(() => detail.value?.status === 'active')

// ---- 模块 tab ----
const activeModule = ref<TeamModule>('members')

// ---------------- 成员 ----------------

const members = ref<TeamMemberItem[]>([])
const membersLoading = ref(false)
const memberKeyword = ref('')
const {
  page: memberPage,
  pageSize: memberPageSize,
  total: memberTotal,
  changePage: changeMemberPage,
  changeSize: changeMemberSize,
  resetPage: resetMemberPage,
  beginLoad: beginMemberLoad,
  isCurrent: isMemberCurrent,
} = usePagination()

async function loadMembers() {
  const seq = beginMemberLoad()
  membersLoading.value = true
  try {
    const result = await adminListTeamMembers(teamId, {
      page: memberPage.value,
      page_size: memberPageSize.value,
      keyword: memberKeyword.value || undefined,
    })
    if (!isMemberCurrent(seq)) return
    members.value = result.items
    memberTotal.value = result.total
  } catch (error) {
    if (!isMemberCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (isMemberCurrent(seq)) membersLoading.value = false
  }
}

function onSearchMembers() {
  resetMemberPage()
  loadMembers()
}

const memberColumns = computed<DataTableColumns<TeamMemberItem>>(() => [
  {
    // 头像独立一列，与昵称列拉开间距
    title: t('admin.teams.avatar'),
    key: 'avatar_url',
    width: 72,
    align: 'center',
    render(row) {
      return h(
        NAvatar,
        { size: 36, round: true, src: row.avatar_url || undefined },
        row.avatar_url ? {} : { default: () => initialOf(row.nickname) },
      )
    },
  },
  {
    title: t('teams.members.user'),
    key: 'nickname',
    minWidth: 200,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'cell-strong' }, row.nickname),
  },
  {
    title: t('teams.role.creator'),
    key: 'role',
    width: 120,
    render(row) {
      const type = row.is_creator ? 'warning' : row.is_admin ? 'info' : 'default'
      const label = row.is_creator
        ? t('teams.role.creator')
        : row.is_admin
          ? t('teams.role.admin')
          : t('teams.role.member')
      return h(NTag, { size: 'small', bordered: false, type }, { default: () => label })
    },
  },
  {
    title: t('teams.members.joinedAt'),
    key: 'joined_at',
    width: 170,
    render: (row) => formatDateTime(row.joined_at),
  },
])

// ---------------- 团队题库 ----------------

const problems = ref<TeamProblemSummary[]>([])
const problemsLoading = ref(false)
const problemKeyword = ref('')
const {
  page: problemPage,
  pageSize: problemPageSize,
  total: problemTotal,
  changePage: changeProblemPage,
  changeSize: changeProblemSize,
  resetPage: resetProblemPage,
  beginLoad: beginProblemLoad,
  isCurrent: isProblemCurrent,
} = usePagination()

async function loadProblems() {
  const seq = beginProblemLoad()
  problemsLoading.value = true
  try {
    const result = await adminListTeamProblems(teamId, {
      page: problemPage.value,
      page_size: problemPageSize.value,
      keyword: problemKeyword.value || undefined,
    })
    if (!isProblemCurrent(seq)) return
    problems.value = result.items
    problemTotal.value = result.total
  } catch (error) {
    if (!isProblemCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (isProblemCurrent(seq)) problemsLoading.value = false
  }
}

function onSearchProblems() {
  resetProblemPage()
  loadProblems()
}

const problemColumns = computed<DataTableColumns<TeamProblemSummary>>(() => [
  {
    title: t('problems.list.name'),
    key: 'title',
    minWidth: 240,
    render(row) {
      return h('div', { class: 'cell-title-wrap' }, [
        h('span', { class: 'cell-title-wrap__text' }, row.title),
        h(
          NTag,
          {
            size: 'tiny',
            bordered: false,
            type: row.referenced_at ? 'info' : 'default',
            style: 'flex-shrink: 0',
          },
          {
            default: () => t(row.referenced_at ? 'admin.teams.referenced' : 'admin.teams.created'),
          },
        ),
      ])
    },
  },
  {
    title: t('admin.teams.status'),
    key: 'status',
    width: 100,
    render(row) {
      const type =
        row.status === 'published' ? 'success' : row.status === 'draft' ? 'warning' : 'default'
      const labelKey =
        row.status === 'published'
          ? 'problems.list.statusPublished'
          : row.status === 'draft'
            ? 'problems.list.statusDraft'
            : 'problems.list.statusArchived'
      return h(NTag, { size: 'small', bordered: false, type }, { default: () => t(labelKey) })
    },
  },
  {
    title: t('admin.teams.problemLimits'),
    key: 'limits',
    width: 150,
    render: (row) => `${row.time_limit_ms ?? '--'} ms / ${row.memory_limit_mb ?? '--'} MB`,
  },
  {
    title: t('admin.teams.problemSubmissions'),
    key: 'counters',
    width: 130,
    align: 'center',
    render: (row) => `${row.submission_count ?? 0} / ${row.accepted_count ?? 0}`,
  },
  {
    title: t('admin.teams.setCreated'),
    key: 'created_at',
    width: 170,
    render: (row) => (row.created_at ? formatDateTime(row.created_at) : '--'),
  },
])

// ---------------- 团队题单 ----------------

const sets = ref<ProblemSetSummary[]>([])
const setsLoading = ref(false)
const setKeyword = ref('')
const {
  page: setPage,
  pageSize: setPageSize,
  total: setTotal,
  changePage: changeSetPage,
  changeSize: changeSetSize,
  resetPage: resetSetPage,
  beginLoad: beginSetLoad,
  isCurrent: isSetCurrent,
} = usePagination()

async function loadSets() {
  const seq = beginSetLoad()
  setsLoading.value = true
  try {
    const result = await adminListTeamProblemSets(teamId, {
      page: setPage.value,
      page_size: setPageSize.value,
      keyword: setKeyword.value || undefined,
    })
    if (!isSetCurrent(seq)) return
    sets.value = result.items
    setTotal.value = result.total
  } catch (error) {
    if (!isSetCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (isSetCurrent(seq)) setsLoading.value = false
  }
}

function onSearchSets() {
  resetSetPage()
  loadSets()
}

const setColumns = computed<DataTableColumns<ProblemSetSummary>>(() => [
  {
    title: t('problemSets.list.titleLabel'),
    key: 'title',
    minWidth: 240,
    render(row) {
      return h('div', { class: 'cell-title-wrap' }, [
        h('span', { class: 'cell-title-wrap__text' }, row.title),
        h(
          NTag,
          {
            size: 'tiny',
            bordered: false,
            type: row.referenced_at ? 'info' : 'default',
            style: 'flex-shrink: 0',
          },
          {
            default: () => t(row.referenced_at ? 'admin.teams.referenced' : 'admin.teams.created'),
          },
        ),
      ])
    },
  },
  {
    title: t('admin.teams.setVisible'),
    key: 'item_count',
    width: 90,
    align: 'center',
    render: (row) => String(row.item_count),
  },
  {
    title: t('problemSets.list.status'),
    key: 'status',
    width: 100,
    render(row) {
      const active = row.status === 'active'
      return h(
        NTag,
        { size: 'small', bordered: false, type: active ? 'info' : 'warning' },
        { default: () => t(active ? 'problemSets.list.active' : 'problemSets.detail.archived') },
      )
    },
  },
  {
    title: t('admin.teams.setCreated'),
    key: 'created_at',
    width: 170,
    render: (row) => formatDateTime(row.created_at),
  },
])

// ---------------- 团队比赛 ----------------

const contests = ref<ContestSummary[]>([])
const contestsLoading = ref(false)
const contestKeyword = ref('')
const {
  page: contestPage,
  pageSize: contestPageSize,
  total: contestTotal,
  changePage: changeContestPage,
  changeSize: changeContestSize,
  resetPage: resetContestPage,
  beginLoad: beginContestLoad,
  isCurrent: isContestCurrent,
} = usePagination()

async function loadContests() {
  const seq = beginContestLoad()
  contestsLoading.value = true
  try {
    const result = await adminListTeamContests(teamId, {
      page: contestPage.value,
      page_size: contestPageSize.value,
      keyword: contestKeyword.value || undefined,
    })
    if (!isContestCurrent(seq)) return
    contests.value = result.items
    contestTotal.value = result.total
  } catch (error) {
    if (!isContestCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (isContestCurrent(seq)) contestsLoading.value = false
  }
}

function onSearchContests() {
  resetContestPage()
  loadContests()
}

const contestColumns = computed<DataTableColumns<ContestSummary>>(() => [
  {
    title: t('contests.list.titleLabel'),
    key: 'title',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'cell-strong' }, row.title),
  },
  {
    title: t('admin.teams.contestRule'),
    key: 'rule_type',
    width: 90,
    render: (row) => row.rule_type,
  },
  {
    title: t('admin.teams.status'),
    key: 'status',
    width: 100,
    render(row) {
      const type =
        row.status === 'running' ? 'success' : row.status === 'scheduled' ? 'info' : 'default'
      const labelKey =
        row.status === 'running'
          ? 'contests.statusRunning'
          : row.status === 'scheduled'
            ? 'contests.statusScheduled'
            : 'contests.statusFinished'
      return h(NTag, { size: 'small', bordered: false, type }, { default: () => t(labelKey) })
    },
  },
  {
    title: t('admin.teams.contestTime'),
    key: 'time',
    minWidth: 300,
    render: (row) => `${formatDateTime(row.start_time)} → ${formatDateTime(row.end_time)}`,
  },
])

// ---------------- 模块懒加载（切到 tab 才拉数据，概要统计随之回填） ----------------

const loadedModules = new Set<TeamModule>()

function ensureModuleLoaded(mod: TeamModule) {
  if (loadedModules.has(mod)) return
  loadedModules.add(mod)
  if (mod === 'members') loadMembers()
  else if (mod === 'problems') loadProblems()
  else if (mod === 'sets') loadSets()
  else loadContests()
}

watch(activeModule, ensureModuleLoaded, { immediate: true })
</script>

<template>
  <WorkbenchShell>
    <!-- 加载失败 / 骨架 -->
    <div v-if="!detail && loadFailed" class="table-fill-empty">
      <n-empty :description="t('admin.teams.loadFailed')" size="large">
        <template #extra>
          <n-button @click="load">{{ t('action.refresh') }}</n-button>
        </template>
      </n-empty>
    </div>
    <n-spin v-else-if="!detail" class="table-fill" content-style="height: 100%" />

    <template v-else>
      <!-- ======== 团队信息卡 ======== -->
      <section class="team-hero">
        <img v-if="detail.avatar_url" :src="detail.avatar_url" alt="" class="team-hero__avatar" />
        <div v-else class="team-hero__avatar team-hero__avatar--fallback" aria-hidden="true">
          {{ initialOf(detail.name) }}
        </div>
        <div class="team-hero__main">
          <div class="team-hero__title-row">
            <h2 class="team-hero__title">{{ detail.name }}</h2>
            <n-tag size="small" round :bordered="false" type="warning">
              {{ t('teams.role.creator') }}：{{ detail.creator_nickname ?? '—' }}
            </n-tag>
            <n-tag size="small" round :bordered="false" :type="isActive ? 'success' : 'error'">
              {{ t(isActive ? 'admin.teams.statusActive' : 'admin.teams.statusDisbanded') }}
            </n-tag>
          </div>
          <p class="team-hero__desc" :class="{ 'team-hero__desc--empty': !detail.description }">
            {{ detail.description ?? t('admin.teams.descEmpty') }}
          </p>
          <div class="team-hero__meta">
            <span>
              {{ t('admin.teams.memberCount') }}
              <strong>{{ detail.member_count }}</strong>
            </span>
            <span class="team-hero__dot" aria-hidden="true">·</span>
            <span>{{ t('admin.teams.createdAt') }} {{ formatDateTime(detail.created_at) }}</span>
            <template v-if="!isActive">
              <span class="team-hero__dot" aria-hidden="true">·</span>
              <span class="team-hero__disbanded">
                {{ t('admin.teams.disbandedAt') }} {{ formatDateTime(detail.disbanded_at) }}
              </span>
            </template>
            <span class="team-hero__dot" aria-hidden="true">·</span>
            <span class="team-hero__id" :title="detail.id">
              {{ t('admin.teams.teamId') }} {{ detail.id.slice(0, 8) }}
            </span>
          </div>
        </div>
        <div class="team-hero__stats">
          <div class="stat">
            <span class="stat__num">{{ detail.problem_count }}</span>
            <span class="stat__label">{{ t('admin.teams.statProblems') }}</span>
          </div>
          <div class="stat">
            <span class="stat__num">{{ detail.problem_set_count }}</span>
            <span class="stat__label">{{ t('admin.teams.statSets') }}</span>
          </div>
          <div class="stat">
            <span class="stat__num">{{ detail.contest_count }}</span>
            <span class="stat__label">{{ t('admin.teams.statContests') }}</span>
          </div>
        </div>
      </section>

      <!-- ======== 模块区（tab 线条直连内容；懒加载切到的模块） ======== -->
      <section class="module-area">
        <n-tabs v-model:value="activeModule" type="line" class="module-tabs">
          <!-- 成员 -->
          <n-tab-pane name="members" :tab="t('admin.teams.tabMembers')">
            <SearchFilterBar
              :keyword="memberKeyword"
              :placeholder="t('teams.members.search')"
              @update:keyword="
                (v: string) => {
                  memberKeyword = v
                }
              "
              @search="onSearchMembers"
              @reset="onSearchMembers"
            >
              <template #actions>
                <RefreshButton
                  :loading="membersLoading"
                  :aria-label="t('action.refresh')"
                  @click="loadMembers"
                />
              </template>
            </SearchFilterBar>
            <PaginatedDataTable
              :columns="memberColumns"
              :data="members"
              :loading="membersLoading"
              :total="memberTotal"
              v-model:page="memberPage"
              v-model:page-size="memberPageSize"
              :page-sizes="[10, 20, 50]"
              :empty-text="t('admin.teams.membersEmpty')"
              :table-props="{ flexHeight: true }"
              @update:page="
                (p: number) => {
                  changeMemberPage(p)
                  loadMembers()
                }
              "
              @update:page-size="
                (s: number) => {
                  changeMemberSize(s)
                  loadMembers()
                }
              "
            />
          </n-tab-pane>

          <!-- 团队题库 -->
          <n-tab-pane name="problems" :tab="t('admin.teams.tabProblems')">
            <SearchFilterBar
              :keyword="problemKeyword"
              :placeholder="t('admin.teams.problemSearch')"
              @update:keyword="
                (v: string) => {
                  problemKeyword = v
                }
              "
              @search="onSearchProblems"
              @reset="onSearchProblems"
            >
              <template #actions>
                <RefreshButton
                  :loading="problemsLoading"
                  :aria-label="t('action.refresh')"
                  @click="loadProblems"
                />
              </template>
            </SearchFilterBar>
            <PaginatedDataTable
              :columns="problemColumns"
              :data="problems"
              :loading="problemsLoading"
              :total="problemTotal"
              v-model:page="problemPage"
              v-model:page-size="problemPageSize"
              :page-sizes="[10, 20, 50]"
              :empty-text="t('admin.teams.problemsEmpty')"
              :table-props="{ flexHeight: true }"
              @update:page="
                (p: number) => {
                  changeProblemPage(p)
                  loadProblems()
                }
              "
              @update:page-size="
                (s: number) => {
                  changeProblemSize(s)
                  loadProblems()
                }
              "
            />
          </n-tab-pane>

          <!-- 团队题单 -->
          <n-tab-pane name="sets" :tab="t('admin.teams.tabSets')">
            <SearchFilterBar
              :keyword="setKeyword"
              :placeholder="t('problemSets.list.search')"
              @update:keyword="
                (v: string) => {
                  setKeyword = v
                }
              "
              @search="onSearchSets"
              @reset="onSearchSets"
            >
              <template #actions>
                <RefreshButton
                  :loading="setsLoading"
                  :aria-label="t('action.refresh')"
                  @click="loadSets"
                />
              </template>
            </SearchFilterBar>
            <PaginatedDataTable
              :columns="setColumns"
              :data="sets"
              :loading="setsLoading"
              :total="setTotal"
              v-model:page="setPage"
              v-model:page-size="setPageSize"
              :page-sizes="[10, 20, 50]"
              :empty-text="t('admin.teams.setsEmpty')"
              :table-props="{ flexHeight: true }"
              @update:page="
                (p: number) => {
                  changeSetPage(p)
                  loadSets()
                }
              "
              @update:page-size="
                (s: number) => {
                  changeSetSize(s)
                  loadSets()
                }
              "
            />
          </n-tab-pane>

          <!-- 团队比赛 -->
          <n-tab-pane name="contests" :tab="t('admin.teams.tabContests')">
            <SearchFilterBar
              :keyword="contestKeyword"
              :placeholder="t('contests.list.search')"
              @update:keyword="
                (v: string) => {
                  contestKeyword = v
                }
              "
              @search="onSearchContests"
              @reset="onSearchContests"
            >
              <template #actions>
                <RefreshButton
                  :loading="contestsLoading"
                  :aria-label="t('action.refresh')"
                  @click="loadContests"
                />
              </template>
            </SearchFilterBar>
            <PaginatedDataTable
              :columns="contestColumns"
              :data="contests"
              :loading="contestsLoading"
              :total="contestTotal"
              v-model:page="contestPage"
              v-model:page-size="contestPageSize"
              :page-sizes="[10, 20, 50]"
              :empty-text="t('admin.teams.contestsEmpty')"
              :table-props="{ flexHeight: true }"
              @update:page="
                (p: number) => {
                  changeContestPage(p)
                  loadContests()
                }
              "
              @update:page-size="
                (s: number) => {
                  changeContestSize(s)
                  loadContests()
                }
              "
            />
          </n-tab-pane>
        </n-tabs>
      </section>
    </template>
  </WorkbenchShell>
</template>

<style scoped>
/* ======== 团队信息卡 ======== */
.team-hero {
  flex-shrink: 0;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 18px 20px;
  margin-bottom: 16px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius, 8px);
  background: var(--app-card-bg);
}
.team-hero__avatar {
  width: 72px;
  height: 72px;
  border-radius: 12px;
  object-fit: cover;
  flex-shrink: 0;
}
.team-hero__avatar--fallback {
  display: grid;
  place-items: center;
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  background: var(--app-primary);
  user-select: none;
}
.team-hero__main {
  flex: 1;
  min-width: 0;
}
.team-hero__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.team-hero__title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--app-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.team-hero__desc {
  margin: 6px 0 8px;
  color: var(--app-text-secondary);
  font-size: 13px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.team-hero__desc--empty {
  color: var(--app-text-secondary);
  opacity: 0.7;
}
.team-hero__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.team-hero__meta strong {
  color: var(--app-primary);
}
.team-hero__dot {
  opacity: 0.5;
}
.team-hero__disbanded {
  color: var(--app-error, #d03050);
}
.team-hero__id {
  font-family: monospace;
}

/* 概要统计 */
.team-hero__stats {
  display: flex;
  gap: 22px;
  flex-shrink: 0;
  padding-left: 22px;
  border-left: 1px solid var(--app-border);
}
.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 56px;
}
.stat__num {
  font-size: 22px;
  font-weight: 700;
  color: var(--app-text);
  line-height: 1.2;
}
.stat__label {
  font-size: 12px;
  color: var(--app-text-secondary);
  white-space: nowrap;
}

/* ======== 模块区：tab 线条直连内容，无卡片外框；高度链打通使表格吃满剩余空间 ======== */
.module-area {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.module-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.module-tabs :deep(.n-tabs-nav) {
  flex-shrink: 0;
}
/* 非 animated 模式 naive 不渲染 pane-wrapper，pane 直接挂在 .n-tabs 下；
   flexHeight 表格经 .table-fill 吃满 pane 高度、表体内部滚动，分页条恒沉底 */
.module-tabs :deep(.n-tabs-pane-wrapper),
.module-tabs :deep(.n-tab-pane) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.module-tabs :deep(.n-tab-pane) {
  padding-top: 8px;
}
.pane-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-shrink: 0;
}
.cell-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.cell-title-wrap__text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cell-strong {
  font-weight: 600;
}

@media (max-width: 900px) {
  .team-hero {
    flex-direction: column;
  }
  .team-hero__stats {
    padding-left: 0;
    padding-top: 12px;
    border-left: none;
    border-top: 1px solid var(--app-border);
    width: 100%;
    justify-content: space-around;
  }
}
</style>
