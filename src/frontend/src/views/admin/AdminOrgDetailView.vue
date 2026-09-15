<script setup lang="ts">
/**
 * 组织管理详情（/admin/orgs/:id，admin 只读浏览，docs/contracts/orgs.md 管理端视图）：
 * 组织信息卡 + 模块化 tab（成员 / 名下团队 / 组织题库，按 tab 懒加载）；
 * 不做维护动作（维护收敛在组织空间 / 团队空间）。
 * 组织题库走组织端点（GET /orgs/{id}/problems）——站点 admin 视同拥有组织管理权（orgs.md）。
 */
import { computed, h, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NCheckbox, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import { adminGetOrg, adminListOrgMembers } from '@/api/admin'
import { listOrgProblems, listOrgTeams } from '@/api/orgs'
import BaseAvatar from '@/components/BaseAvatar.vue'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { formatDateTime } from '@/utils/format'
import { renderDifficulty, renderRatio } from '@/utils/problemCells'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import type { OrgDetail, OrgMemberItem, TeamProblemSummary, TeamSummary } from '@/types'

const route = useRoute()
const { t } = useI18n()

const orgId = String(route.params.id)
const org = ref<OrgDetail | null>(null)
const loading = ref(false)

// ---------------- 模块 tab（成员 / 名下团队 / 组织题库；按 tab 懒加载） ----------------

type OrgModule = 'members' | 'teams' | 'problems'
const activeModule = ref<OrgModule>('members')
const loadedModules = new Set<OrgModule>()

function ensureModuleLoaded(mod: OrgModule) {
  if (loadedModules.has(mod)) return
  loadedModules.add(mod)
  if (mod === 'members') void loadMembers()
  else if (mod === 'teams') void loadTeams()
  else void loadProblems()
}

watch(activeModule, ensureModuleLoaded, { immediate: true })

async function loadOrg() {
  loading.value = true
  try {
    org.value = await adminGetOrg(orgId)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('admin.orgs.loadFailed'))
  } finally {
    loading.value = false
  }
}

// ---------------- 成员（admin 管理视图） ----------------

const members = ref<OrgMemberItem[]>([])
const membersLoading = ref(false)
const memberKeyword = ref('')
const {
  page: memberPage,
  pageSize: memberPageSize,
  total: memberTotal,
  changePage: changeMemberPage,
  resetPage: resetMemberPage,
} = usePagination()

async function loadMembers() {
  membersLoading.value = true
  try {
    const result = await adminListOrgMembers(orgId, {
      page: memberPage.value,
      page_size: memberPageSize.value,
      keyword: memberKeyword.value || undefined,
    })
    members.value = result.items
    memberTotal.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    membersLoading.value = false
  }
}

function searchMembers() {
  resetMemberPage()
  loadMembers()
}

const memberColumns = computed<DataTableColumns<OrgMemberItem>>(() => [
  {
    title: t('admin.orgs.tabMembers'),
    key: 'nickname',
    minWidth: 200,
    ellipsis: { tooltip: true },
    render(row) {
      return h('div', { class: 'cell-user' }, [
        h(BaseAvatar, { src: row.avatar_url, name: row.nickname, size: 32 }),
        h('span', { class: 'cell-strong' }, row.nickname),
      ])
    },
  },
  {
    title: t('orgs.role.admin'),
    key: 'role',
    width: 130,
    render(row) {
      return h(
        NTag,
        { size: 'small', bordered: false, type: row.is_admin ? 'info' : 'default' },
        { default: () => t(row.is_admin ? 'orgs.role.admin' : 'orgs.role.member') },
      )
    },
  },
  {
    title: t('orgs.members.note'),
    key: 'note',
    minWidth: 140,
    ellipsis: { tooltip: true },
    render: (row) => row.note ?? '—',
  },
  {
    title: t('orgs.members.joinedAt'),
    key: 'joined_at',
    width: 170,
    render: (row) => formatDateTime(row.joined_at),
  },
])

// ---------------- 名下团队（org 端点对 admin 放行，只读浏览） ----------------

const teams = ref<TeamSummary[]>([])
const teamsLoading = ref(false)
const teamKeyword = ref('')
const {
  page: teamPage,
  pageSize: teamPageSize,
  total: teamTotal,
  changePage: changeTeamPage,
  resetPage: resetTeamPage,
} = usePagination()

async function loadTeams() {
  teamsLoading.value = true
  try {
    const result = await listOrgTeams(orgId, {
      page: teamPage.value,
      page_size: teamPageSize.value,
      keyword: teamKeyword.value || undefined,
    })
    teams.value = result.items
    teamTotal.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    teamsLoading.value = false
  }
}

function searchTeams() {
  resetTeamPage()
  loadTeams()
}

const teamColumns = computed<DataTableColumns<TeamSummary>>(() => [
  {
    title: t('admin.teams.team'),
    key: 'name',
    minWidth: 200,
    ellipsis: { tooltip: true },
    render(row) {
      return h('div', { class: 'cell-user' }, [
        h(BaseAvatar, { src: row.avatar_url, name: row.name, size: 32, kind: 'team' }),
        h('span', { class: 'cell-strong' }, row.name),
      ])
    },
  },
  {
    title: t('admin.orgs.teamVisibility'),
    key: 'visibility',
    width: 100,
    render: (row) =>
      h(
        NTag,
        { size: 'small', bordered: false, type: row.visibility === 'public' ? 'success' : 'default' },
        {
          default: () =>
            t(
              row.visibility === 'public'
                ? 'teams.settings.visibilityPublic'
                : 'teams.settings.visibilityPrivate',
            ),
        },
      ),
  },
  {
    title: t('admin.orgs.memberCount'),
    key: 'member_count',
    width: 80,
    align: 'center',
    render: (row) => String(row.member_count),
  },
  {
    title: t('admin.orgs.createdAt'),
    key: 'created_at',
    width: 170,
    render: (row) => formatDateTime(row.created_at),
  },
])

// ---------------- 组织题库（org 端点对 admin 放行，只读浏览；含草稿） ----------------

const problems = ref<TeamProblemSummary[]>([])
const problemsLoading = ref(false)
const problemKeyword = ref('')
const problemDraftOnly = ref(false)
const {
  page: problemPage,
  pageSize: problemPageSize,
  total: problemTotal,
  changePage: changeProblemPage,
  resetPage: resetProblemPage,
} = usePagination()

async function loadProblems() {
  problemsLoading.value = true
  try {
    const result = await listOrgProblems(orgId, {
      page: problemPage.value,
      page_size: problemPageSize.value,
      keyword: problemKeyword.value || undefined,
      status: problemDraftOnly.value ? 'draft' : undefined,
    })
    problems.value = result.items
    problemTotal.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    problemsLoading.value = false
  }
}

function searchProblems() {
  resetProblemPage()
  loadProblems()
}

function onToggleDraftBox(checked: boolean) {
  problemDraftOnly.value = checked
  resetProblemPage()
  loadProblems()
}

const problemColumns = computed<DataTableColumns<TeamProblemSummary>>(() => [
  {
    title: t('problems.list.name'),
    key: 'title',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'cell-strong' }, row.title),
  },
  {
    title: t('problems.manage.shareTitle'),
    key: 'publish',
    width: 110,
    render: (row) => {
      // 已验题后才可能「需重新验题」（草稿从未验题 → 显示未验题）
      if (row.is_verified && row.needs_reverification) {
        return h(
          NTag,
          { size: 'small', bordered: false, type: 'warning' },
          { default: () => t('problems.manage.reverifyTag') },
        )
      }
      return h(
        NTag,
        { size: 'small', bordered: false, type: row.is_verified ? 'success' : 'default' },
        {
          default: () =>
            row.is_verified ? t('problems.manage.verifiedTag') : t('problems.manage.unverifiedTag'),
        },
      )
    },
  },
  {
    title: t('problems.list.difficulty'),
    key: 'difficulty',
    width: 80,
    align: 'center',
    render: (row) => renderDifficulty(row),
  },
  {
    title: t('problems.list.limits'),
    key: 'limits',
    width: 150,
    render: (row) => `${row.time_limit_ms ?? '--'} ms / ${row.memory_limit_mb ?? '--'} MB`,
  },
  {
    title: t('problems.list.passRate'),
    key: 'rate',
    width: 100,
    align: 'center',
    render: (row) => renderRatio(row),
  },
  {
    title: t('admin.orgs.createdAt'),
    key: 'created_at',
    width: 170,
    render: (row) => formatDateTime(row.created_at),
  },
])

onMounted(() => {
  loadOrg()
})
</script>

<template>
  <WorkbenchShell :title="t('admin.orgs.detailTitle')">
    <!-- 组织信息卡 -->
    <section class="org-card">
      <BaseAvatar
        kind="team"
        :src="org?.avatar_url"
        :name="org?.name ?? ''"
        :size="56"
        :round="false"
        :radius="8"
        bordered
      />
      <div class="org-card__body">
        <div class="org-card__head">
          <h2 class="org-card__name">{{ org?.name ?? '—' }}</h2>
          <NTag
            v-if="org"
            size="small"
            :bordered="false"
            :type="org.status === 'active' ? 'success' : 'error'"
          >
            {{ t(org.status === 'active' ? 'admin.orgs.statusActive' : 'admin.orgs.statusDisbanded') }}
          </NTag>
        </div>
        <p class="org-card__desc" :class="{ 'org-card__desc--empty': !org?.description }">
          {{ org?.description ?? t('admin.orgs.descEmpty') }}
        </p>
        <div class="org-card__meta">
          <span>
            {{ t('admin.orgs.memberCount') }}
            <strong>{{ org?.member_count ?? '—' }}</strong>
          </span>
          <span>
            {{ t('admin.orgs.teamCount') }}
            <strong>{{ org?.team_count ?? '—' }}</strong>
          </span>
          <span>
            {{ t('admin.orgs.createdAt') }}
            <strong>{{ org ? formatDateTime(org.created_at) : '—' }}</strong>
          </span>
          <span class="org-card__id">{{ t('admin.orgs.orgId') }} {{ orgId }}</span>
        </div>
      </div>
    </section>

    <!-- 模块 tab：成员 / 名下团队 / 组织题库（与团队管理详情同款 tab 结构） -->
    <n-tabs v-model:value="activeModule" type="line" class="module-tabs">
      <!-- 成员 -->
      <n-tab-pane name="members" :tab="t('admin.orgs.tabMembers')">
        <div class="tab-toolbar">
          <SearchFilterBar
            :keyword="memberKeyword"
            :placeholder="t('orgs.members.search')"
            search-width="220px"
            @update:keyword="
              (v: string) => {
                memberKeyword = v
              }
            "
            @search="searchMembers"
            @reset="searchMembers"
          >
            <template #actions>
              <RefreshButton
                :loading="membersLoading"
                :aria-label="t('action.refresh')"
                @click="loadMembers"
              />
            </template>
          </SearchFilterBar>
        </div>
        <PaginatedDataTable
          :columns="memberColumns"
          :data="members"
          :loading="membersLoading"
          :total="memberTotal"
          :page="memberPage"
          :page-size="memberPageSize"
          :empty-text="t('admin.orgs.membersEmpty')"
          :table-props="{ size: 'small' }"
          @update:page="
            (p: number) => {
              changeMemberPage(p)
              loadMembers()
            }
          "
        />
      </n-tab-pane>

      <!-- 名下团队 -->
      <n-tab-pane name="teams" :tab="t('admin.orgs.tabTeams')">
        <div class="tab-toolbar">
          <SearchFilterBar
            :keyword="teamKeyword"
            :placeholder="t('orgs.teams.search')"
            search-width="220px"
            @update:keyword="
              (v: string) => {
                teamKeyword = v
              }
            "
            @search="searchTeams"
            @reset="searchTeams"
          >
            <template #actions>
              <RefreshButton
                :loading="teamsLoading"
                :aria-label="t('action.refresh')"
                @click="loadTeams"
              />
            </template>
          </SearchFilterBar>
        </div>
        <PaginatedDataTable
          :columns="teamColumns"
          :data="teams"
          :loading="teamsLoading"
          :total="teamTotal"
          :page="teamPage"
          :page-size="teamPageSize"
          :empty-text="t('admin.orgs.teamsEmpty')"
          :table-props="{ size: 'small' }"
          @update:page="
            (p: number) => {
              changeTeamPage(p)
              loadTeams()
            }
          "
        />
      </n-tab-pane>

      <!-- 组织题库 -->
      <n-tab-pane name="problems" :tab="t('admin.orgs.tabProblems')">
        <div class="tab-toolbar">
          <SearchFilterBar
            :keyword="problemKeyword"
            :placeholder="t('orgs.problems.search')"
            search-width="220px"
            @update:keyword="
              (v: string) => {
                problemKeyword = v
              }
            "
            @search="searchProblems"
            @reset="searchProblems"
          >
            <template #actions>
              <NCheckbox
                :checked="problemDraftOnly"
                @update:checked="onToggleDraftBox"
              >
                {{ t('orgs.problems.draftBox') }}
              </NCheckbox>
              <RefreshButton
                :loading="problemsLoading"
                :aria-label="t('action.refresh')"
                @click="loadProblems"
              />
            </template>
          </SearchFilterBar>
        </div>
        <PaginatedDataTable
          :columns="problemColumns"
          :data="problems"
          :loading="problemsLoading"
          :total="problemTotal"
          :page="problemPage"
          :page-size="problemPageSize"
          :empty-text="t('orgs.problems.empty')"
          :table-props="{ size: 'small' }"
          @update:page="
            (p: number) => {
              changeProblemPage(p)
              loadProblems()
            }
          "
        />
      </n-tab-pane>
    </n-tabs>
  </WorkbenchShell>
</template>

<style scoped>
/* 信息卡：平面边框卡，不做维护动作 */
.org-card {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 18px 20px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-card-bg, #fff);
  margin-bottom: 16px;
}
.org-card__body {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 6px;
}
.org-card__head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.org-card__name {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--app-text);
}
.org-card__desc {
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 13px;
  line-height: 1.55;
}
.org-card__desc--empty {
  opacity: 0.55;
}
.org-card__meta {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  color: var(--app-text-secondary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.org-card__meta strong {
  color: var(--app-text);
  font-weight: 600;
  margin-left: 2px;
}
.org-card__id {
  word-break: break-all;
}
.section-head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin: 16px 0 10px;
}
.section-head__title {
  font-size: 14px;
  font-weight: 650;
  color: var(--app-text);
}
/* 模块 tab（与团队管理详情同款）：tab 线条直连内容区 */
.module-tabs {
  margin-top: 4px;
}
.tab-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.cell-user {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.cell-strong {
  font-weight: 600;
}
</style>
