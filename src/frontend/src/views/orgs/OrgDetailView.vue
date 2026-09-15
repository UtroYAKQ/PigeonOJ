<script setup lang="ts">
/**
 * 组织详情（/orgs/:id，docs/contracts/orgs.md）：组织空间式布局。
 * Hero（头像 + 名称 + 简介 + 动作区）+ 模块化内容区：
 * 成员 / 组织团队 / 组织题库 / 组织设置。
 * 权限按 my_role 显隐（org_admin ⊇ org_member）；组织题库为封闭上下文——
 * 列表走组织端点，题目编辑复用题库统一端点（行点击进编辑向导，仅创建走组织端点）；
 * 非成员访问返回 2003，页面呈现无权访问态（组织无申请加入通道）。
 */
import { computed, h, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { DataTableColumns } from 'naive-ui'
import { CirclePlus, Collection, MoreFilled, Setting, UserFilled } from '@element-plus/icons-vue'
import {
  NButton,
  NCheckbox,
  NDropdown,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NForm,
  NFormItem,
  NIcon,
  NInput,
  NModal,
  NTag,
} from 'naive-ui'

import {
  addOrgMembers,
  createOrgTeam,
  disbandOrg,
  getOrg,
  listOrgMembers,
  listOrgProblems,
  listOrgTeams,
  removeOrgMember,
  setOrgMemberAdmin,
  setOrgMemberNote,
  updateOrg,
} from '@/api/orgs'
import { uploadImage } from '@/api/files'
import { ApiError } from '@/api/http'
import BaseAvatar from '@/components/BaseAvatar.vue'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { formatCompact, formatDateTime } from '@/utils/format'
import { renderDifficulty, renderRatio } from '@/utils/problemCells'
import { useUserStore } from '@/stores/user'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import type { OrgDetail, OrgMemberItem, TeamProblemSummary, TeamSummary } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const orgId = String(route.params.id)
const org = ref<OrgDetail | null>(null)
const loadFailed = ref(false)
/** 403（非组织成员）标志：失败态下呈现无权访问提示而非裸错误 */
const forbidden = ref(false)
const loading = ref(false)

/** 组织管理员（org_admin；站点 admin 视同拥有全部组织管理权，docs/contracts/orgs.md） */
const isOrgAdmin = computed(() => org.value?.my_role === 'admin' || userStore.isAdmin)
/** 可见组织工作台（组织成员 my_role 非空；站点 admin 免成员校验） */
const isMember = computed(() => org.value?.my_role != null || userStore.isAdmin)
/** 站点 admin 且非组织成员：hero 显示站点管理员身份标签 */
const isSiteAdminViewer = computed(() => userStore.isAdmin && !org.value?.my_role)

/** 复制组织 ID（统计行）：显示前 8 位，复制完整 ID */
async function copyOrgId() {
  try {
    await navigator.clipboard.writeText(orgId)
    message.success(t('problems.detail.copied'))
  } catch {
    message.error(t('common.operationFailed'))
  }
}

// ---------------- 模块 tab（内容板块） ----------------

type OrgModule = 'members' | 'teams' | 'problems' | 'settings'
const activeModule = ref<OrgModule>('members')

const moduleMeta = computed(() => [
  { key: 'members' as OrgModule, labelKey: 'orgs.detail.tabMembers', icon: Setting },
  { key: 'teams' as OrgModule, labelKey: 'orgs.detail.tabTeams', icon: UserFilled },
  { key: 'problems' as OrgModule, labelKey: 'orgs.detail.tabProblems', icon: Collection },
])

// ---------------- 成员 ----------------

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
    const result = await listOrgMembers(orgId, {
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

/** 成员行操作（⋯ 下拉）：备注（本人 / org_admin）、授·撤管理员、移出（org_admin） */
type MemberAction = 'grant' | 'revoke' | 'kick' | 'note'

function memberActions(row: OrgMemberItem): Array<{ key: MemberAction; label: string }> {
  const actions: Array<{ key: MemberAction; label: string }> = []
  if (row.user_id === userStore.user?.id || isOrgAdmin.value) {
    actions.push({ key: 'note', label: t('orgs.members.note') })
  }
  if (isOrgAdmin.value) {
    actions.push({
      key: row.is_admin ? 'revoke' : 'grant',
      label: t(row.is_admin ? 'orgs.members.revokeAdmin' : 'orgs.members.grantAdmin'),
    })
  }
  // 移出不提供给自己一行（无退出组织通道，避免误操作后失去自身管理权）
  if (isOrgAdmin.value && row.user_id !== userStore.user?.id) {
    actions.push({ key: 'kick', label: t('orgs.members.kick') })
  }
  return actions
}

function onMemberAction(action: MemberAction, row: OrgMemberItem) {
  if (action === 'grant' || action === 'revoke') {
    void onSetAdmin(row, action === 'grant')
    return
  }
  if (action === 'note') {
    noteTarget.value = row
    noteValue.value = row.note ?? ''
    noteVisible.value = true
    return
  }
  onKick(row)
}

/** 备注编辑弹窗（本人 / org_admin 共用；空值 = 清除备注） */
const noteVisible = ref(false)
const noteTarget = ref<OrgMemberItem | null>(null)
const noteValue = ref('')
const noteSaving = ref(false)

async function onNoteSave() {
  if (!noteTarget.value) return
  noteSaving.value = true
  try {
    await setOrgMemberNote(orgId, noteTarget.value.user_id, noteValue.value.trim() || null)
    message.success(t('orgs.members.noteSuccess'))
    noteVisible.value = false
    await loadMembers()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    noteSaving.value = false
  }
}

async function onSetAdmin(row: OrgMemberItem, grant: boolean) {
  try {
    await setOrgMemberAdmin(orgId, row.user_id, grant)
    message.success(t(grant ? 'orgs.members.grantSuccess' : 'orgs.members.revokeSuccess'))
    await loadMembers()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

function onKick(row: OrgMemberItem) {
  confirmAsyncDialog({
    title: t('orgs.members.kick'),
    content: t('orgs.members.kickConfirm', { name: row.nickname }),
    positiveText: t('orgs.members.kick'),
    action: async () => {
      await removeOrgMember(orgId, row.user_id)
    },
    successMessage: t('orgs.members.kickSuccess'),
    onAfterSuccess: () => {
      loadMembers()
      load()
    },
  })
}

const memberColumns = computed<DataTableColumns<OrgMemberItem>>(() => [
  {
    title: t('orgs.members.search'),
    key: 'nickname',
    minWidth: 200,
    ellipsis: { tooltip: true },
    render(row) {
      return h('div', { class: 'cell-user' }, [
        h(BaseAvatar, { src: row.avatar_url, name: row.nickname, size: 32 }),
        h('span', { class: 'cell-strong' }, row.nickname),
        row.user_id === userStore.user?.id
          ? h('span', { class: 'cell-you' }, t('orgs.members.you'))
          : null,
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
        {
          default: () => t(row.is_admin ? 'orgs.role.admin' : 'orgs.role.member'),
        },
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
    render: (row) => formatCompact(row.joined_at),
  },
  ...(isOrgAdmin.value || isMember.value
    ? [
        {
          title: '',
          key: 'ops',
          width: 48,
          render: (row: OrgMemberItem) =>
            memberActions(row).length
              ? h(
                  NDropdown,
                  {
                    trigger: 'click',
                    options: memberActions(row).map((a) => ({ key: a.key, label: a.label })),
                    onSelect: (key: MemberAction) => onMemberAction(key, row),
                  },
                  {
                    default: () =>
                      h(
                        NButton,
                        { circle: true, quaternary: true, size: 'tiny', 'aria-label': t('orgs.detail.more') },
                        { icon: () => h(NIcon, { component: MoreFilled }) },
                      ),
                  },
                )
              : null,
        },
      ]
    : []),
])

// ---- 添加成员（org_admin：单个 UUID + 批量 textarea） ----

const showAddMember = ref(false)
const addingMember = ref(false)
const addForm = ref({ userId: '', batch: '' })

function openAddMember() {
  addForm.value = { userId: '', batch: '' }
  showAddMember.value = true
}

async function doAddMembers() {
  const ids = new Set<string>()
  if (addForm.value.userId.trim()) ids.add(addForm.value.userId.trim())
  for (const line of addForm.value.batch.split(/\r?\n/)) {
    const id = line.trim()
    if (id) ids.add(id)
  }
  if (!ids.size) {
    message.warning(t('orgs.members.userIdPlaceholder'))
    return
  }
  addingMember.value = true
  try {
    await addOrgMembers(orgId, [...ids])
    message.success(t('orgs.members.addSuccess'))
    showAddMember.value = false
    await loadMembers()
    load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    addingMember.value = false
  }
}

// ---------------- 组织团队 ----------------

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
    title: t('teams.list.name'),
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
    title: t('teams.list.description'),
    key: 'description',
    minWidth: 180,
    ellipsis: { tooltip: true },
    render: (row) => row.description ?? '—',
  },
  {
    title: t('teams.settings.visibility'),
    key: 'visibility',
    width: 90,
    render: (row) =>
      h(
        NTag,
        { size: 'small', bordered: false, type: row.visibility === 'public' ? 'success' : 'default' },
        {
          default: () =>
            t(row.visibility === 'public' ? 'teams.settings.visibilityPublic' : 'teams.settings.visibilityPrivate'),
        },
      ),
  },
  {
    title: t('orgs.teams.memberCount'),
    key: 'member_count',
    width: 80,
    align: 'center',
    render: (row) => String(row.member_count),
  },
  {
    title: t('teams.list.createdAt'),
    key: 'created_at',
    width: 170,
    render: (row) => formatDateTime(row.created_at),
  },
])

function rowPropsOfTeam(row: TeamSummary) {
  return { style: 'cursor: pointer;', onClick: () => router.push(`/teams/${row.id}`) }
}

/** 创建团队（org_admin；teams.org_id 固定为本组织，创建者自动 team_creator） */
const showCreateTeam = ref(false)
const creatingTeam = ref(false)
const teamForm = ref({ name: '', description: '', visibility: 'private' as 'public' | 'private' })

function openCreateTeam() {
  teamForm.value = { name: '', description: '', visibility: 'private' }
  showCreateTeam.value = true
}

async function doCreateTeam() {
  if (!teamForm.value.name.trim()) {
    message.warning(t('teams.create.nameRequired'))
    return
  }
  creatingTeam.value = true
  try {
    await createOrgTeam(orgId, {
      name: teamForm.value.name.trim(),
      description: teamForm.value.description.trim() || undefined,
      visibility: teamForm.value.visibility,
    })
    message.success(t('orgs.teams.created'))
    showCreateTeam.value = false
    await loadTeams()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    creatingTeam.value = false
  }
}

// ---------------- 组织题库 ----------------

const problems = ref<TeamProblemSummary[]>([])
const problemsLoading = ref(false)
const problemKeyword = ref('')
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
      status: draftOnly.value ? 'draft' : undefined,
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

/** 草稿箱勾选：勾选后列表查询全组织草稿题目（后端 status=draft 过滤） */
const draftOnly = ref(false)

function onToggleDraftBox(checked: boolean) {
  draftOnly.value = checked
  resetProblemPage()
  loadProblems()
}

/** 创建题目（组织成员 my_role 非空）：进组织题目创建向导（POST /orgs/{orgId}/problems） */
function openProblemCreate() {
  void router.push(`/me/orgs/${orgId}/problems/new`)
}

/** 行点击进组织题目编辑向导（题面 / 测试点 / 验题复用题库统一端点） */
function rowPropsOfProblem(row: TeamProblemSummary) {
  return {
    style: 'cursor: pointer;',
    onClick: () => void router.push(`/me/orgs/${orgId}/problems/${row.id}/edit/statement`),
  }
}

const problemColumns = computed<DataTableColumns<TeamProblemSummary>>(() => [
  {
    title: t('problems.list.name'),
    key: 'title',
    minWidth: 200,
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
    width: 110,
    align: 'center',
    render: (row) => renderRatio(row),
  },
])

// ---------------- 组织信息（编辑抽屉 / 解散） ----------------

const showSettings = ref(false)
const form = ref({ name: '', description: '', avatar_url: '' as string | null })
const saving = ref(false)
const uploadingAvatar = ref(false)

function openSettings() {
  if (!org.value) return
  form.value = {
    name: org.value.name,
    description: org.value.description ?? '',
    avatar_url: org.value.avatar_url ?? '',
  }
  showSettings.value = true
}

async function onAvatarChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploadingAvatar.value = true
  try {
    const result = await uploadImage(file)
    form.value.avatar_url = result.url
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.imageUploadFailed'))
  } finally {
    uploadingAvatar.value = false
    input.value = ''
  }
}

async function saveSettings() {
  if (!form.value.name.trim()) {
    message.warning(t('orgs.create.nameRequired'))
    return
  }
  saving.value = true
  try {
    org.value = await updateOrg(orgId, {
      name: form.value.name.trim(),
      description: form.value.description.trim() || undefined,
      avatar_url: form.value.avatar_url || undefined,
    })
    message.success(t('orgs.settings.saved'))
    showSettings.value = false
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    saving.value = false
  }
}

/** 解散组织（仅站点 admin；软解散，题库题目归档、授权全清） */
function onDisband() {
  confirmAsyncDialog({
    title: t('orgs.settings.disband'),
    content: t('orgs.settings.disbandConfirm'),
    positiveText: t('orgs.settings.disband'),
    action: async () => {
      await disbandOrg(orgId)
    },
    successMessage: t('orgs.settings.disbandSuccess'),
    onAfterSuccess: () => {
      void router.push('/me/orgs/mine')
    },
  })
}

// ---------------- 初始化 ----------------

async function load() {
  loading.value = true
  try {
    org.value = await getOrg(orgId)
    loadFailed.value = false
    forbidden.value = false
  } catch (error) {
    loadFailed.value = true
    // 2003 = 非组织成员（组织空间仅成员可访问）：呈现无权访问态
    forbidden.value = error instanceof ApiError && error.code === 2003
    message.error(error instanceof Error ? error.message : t('orgs.detail.loadFailed'))
  } finally {
    loading.value = false
  }
}

watch(
  () => org.value?.id,
  () => {
    if (org.value) {
      loadMembers()
      loadTeams()
      loadProblems()
    }
  },
)

onMounted(load)
</script>

<template>
  <WorkbenchShell>
    <div class="org-fill">
      <!-- NSpin 只包 Hero（骨架 / 失败 / 信息），不参与模块卡的高度传导 -->
      <NSpin :show="loading" class="hero-spin">
        <!-- 加载骨架 -->
        <div v-if="!org && loading" class="hero hero--skeleton">
          <NSkeleton height="96px" :sharp="false" style="border-radius: 8px" />
          <NSkeleton text style="width: 30%" />
          <NSkeleton text style="width: 60%" />
        </div>

        <!-- 加载失败（403 = 非组织成员：无申请加入通道，仅提示） -->
        <div v-else-if="!org && loadFailed" class="hero hero--failed">
          <NEmpty
            :description="forbidden ? t('orgs.detail.forbidden') : t('orgs.detail.loadFailed')"
            size="large"
          >
            <template #extra>
              <NButton @click="load">{{ t('action.refresh') }}</NButton>
            </template>
          </NEmpty>
        </div>
      </NSpin>

      <!-- ======== Hero（不参与模块卡高度链） ======== -->
      <section v-if="org" class="hero">
        <div class="hero__banner" aria-hidden="true">
          <span class="hero__orb"></span>
          <span class="hero__ring"></span>
        </div>
        <BaseAvatar
          kind="team"
          :src="org.avatar_url"
          :name="org.name"
          :size="64"
          :round="false"
          :radius="10"
          class="hero__avatar"
        />
        <div class="hero__main">
          <div class="hero__title-row">
            <h1 class="hero__title">{{ org.name }}</h1>
            <NTag v-if="org.status === 'disbanded'" size="small" type="error" :bordered="false">
              {{ t('orgs.detail.statusDisbanded') }}
            </NTag>
            <NTag
              v-else-if="org.my_role"
              size="small"
              type="info"
              :bordered="false"
            >
              {{ t(org.my_role === 'admin' ? 'orgs.role.admin' : 'orgs.role.member') }}
            </NTag>
            <NTag v-else-if="isSiteAdminViewer" size="small" type="warning" :bordered="false">
              {{ t('orgs.role.siteAdmin') }}
            </NTag>
          </div>
          <p class="hero__desc" :class="{ 'hero__desc--empty': !org.description }">
            {{ org.description ?? t('orgs.detail.descEmpty') }}
          </p>
          <!-- 统计行：成员数 / 团队数 / 创建时间 / 组织 ID（点击复制完整 ID） -->
          <div class="hero__meta">
            <span>
              {{ t('orgs.list.memberCount') }}
              <strong class="hero__meta-num">{{ org.member_count }}</strong>
            </span>
            <span class="hero__dot" aria-hidden="true">·</span>
            <span>
              {{ t('orgs.list.teamCount') }}
              <strong class="hero__meta-num">{{ org.team_count }}</strong>
            </span>
            <span class="hero__dot" aria-hidden="true">·</span>
            <span>{{ t('orgs.list.createdAt') }} {{ formatDateTime(org.created_at) }}</span>
            <span class="hero__dot" aria-hidden="true">·</span>
            <button type="button" class="hero__id" :title="t('orgs.detail.orgId')" @click="copyOrgId">
              {{ t('orgs.detail.orgId') }} {{ orgId.slice(0, 8) }}
            </button>
          </div>
        </div>

        <!-- 动作区：org_admin 编辑信息；站点 admin 解散组织 -->
        <div class="hero__actions">
          <NButton v-if="isOrgAdmin" secondary size="large" @click="openSettings">
            <template #icon>
              <NIcon :component="Setting" />
            </template>
            {{ t('orgs.detail.editInfo') }}
          </NButton>
          <NButton
            v-if="userStore.isAdmin"
            type="error"
            secondary
            size="large"
            @click="onDisband"
          >
            {{ t('orgs.settings.disband') }}
          </NButton>
        </div>
      </section>

      <!-- ======== 内容模块（tab 线条直连内容） ======== -->
      <section v-if="org" class="module-area">
        <n-tabs v-model:value="activeModule" type="line" class="module-tabs">
          <n-tab-pane
            v-for="moduleItem in moduleMeta"
            :key="moduleItem.key"
            :name="moduleItem.key"
            :tab="t(moduleItem.labelKey)"
          >
            <!-- 成员 -->
            <template v-if="moduleItem.key === 'members'">
              <SearchFilterBar
                :keyword="memberKeyword"
                :placeholder="t('orgs.members.search')"
                @update:keyword="
                  (v: string) => {
                    memberKeyword = v
                  }
                "
                @search="searchMembers"
                @reset="searchMembers"
              >
                <template #actions>
                  <NButton v-if="isOrgAdmin" size="small" type="primary" secondary @click="openAddMember">
                    <template #icon>
                      <NIcon :component="CirclePlus" />
                    </template>
                    {{ t('orgs.members.add') }}
                  </NButton>
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
                :page="memberPage"
                :page-size="memberPageSize"
                :empty-text="t('orgs.members.empty')"
                :table-props="{ size: 'small' }"
                @update:page="
                  (p: number) => {
                    changeMemberPage(p)
                    loadMembers()
                  }
                "
              />
            </template>

            <!-- 组织团队 -->
            <template v-else-if="moduleItem.key === 'teams'">
              <SearchFilterBar
                :keyword="teamKeyword"
                :placeholder="t('orgs.teams.search')"
                @update:keyword="
                  (v: string) => {
                    teamKeyword = v
                  }
                "
                @search="searchTeams"
                @reset="searchTeams"
              >
                <template #actions>
                  <NButton v-if="isOrgAdmin" size="small" type="primary" @click="openCreateTeam">
                    <template #icon>
                      <NIcon :component="CirclePlus" />
                    </template>
                    {{ t('orgs.teams.create') }}
                  </NButton>
                  <RefreshButton
                    :loading="teamsLoading"
                    :aria-label="t('action.refresh')"
                    @click="loadTeams"
                  />
                </template>
              </SearchFilterBar>
              <PaginatedDataTable
                :columns="teamColumns"
                :data="teams"
                :loading="teamsLoading"
                :total="teamTotal"
                :page="teamPage"
                :page-size="teamPageSize"
                :empty-text="t('orgs.teams.empty')"
                :table-props="{
                  size: 'small',
                  rowKey: (row: TeamSummary) => row.id,
                  rowProps: rowPropsOfTeam,
                }"
                @update:page="
                  (p: number) => {
                    changeTeamPage(p)
                    loadTeams()
                  }
                "
              />
            </template>

            <!-- 组织题库 -->
            <template v-else-if="moduleItem.key === 'problems'">
              <SearchFilterBar
                :keyword="problemKeyword"
                :placeholder="t('orgs.problems.search')"
                @update:keyword="
                  (v: string) => {
                    problemKeyword = v
                  }
                "
                @search="searchProblems"
                @reset="searchProblems"
              >
                <template #actions>
                  <NButton v-if="isMember" size="small" secondary @click="openProblemCreate">
                    <template #icon>
                      <NIcon :component="Collection" />
                    </template>
                    {{ t('orgs.problems.create') }}
                  </NButton>
                  <NCheckbox :checked="draftOnly" @update:checked="onToggleDraftBox">
                    {{ t('orgs.problems.draftBox') }}
                  </NCheckbox>
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
                :page="problemPage"
                :page-size="problemPageSize"
                :empty-text="t(draftOnly ? 'orgs.problems.draftsEmpty' : 'orgs.problems.empty')"
                :table-props="{
                  size: 'small',
                  rowKey: (row: TeamProblemSummary) => row.id,
                  rowProps: rowPropsOfProblem,
                }"
                @update:page="
                  (p: number) => {
                    changeProblemPage(p)
                    loadProblems()
                  }
                "
              />
            </template>
          </n-tab-pane>
        </n-tabs>
      </section>
    </div>

    <!-- 成员备注弹窗：本人 / org_admin 共用；空值 = 清除备注 -->
    <NModal
      v-model:show="noteVisible"
      preset="card"
      style="width: 400px"
      :title="t('orgs.members.noteTarget', { name: noteTarget?.nickname ?? '' })"
    >
      <NInput
        v-model:value="noteValue"
        :placeholder="t('orgs.members.notePlaceholder')"
        :maxlength="64"
        show-count
        clearable
        @keyup.enter="onNoteSave"
      />
      <template #footer>
        <div class="modal-actions">
          <NButton size="small" quaternary @click="noteVisible = false">
            {{ t('action.cancel') }}
          </NButton>
          <NButton size="small" type="primary" :loading="noteSaving" @click="onNoteSave">
            {{ t('action.save') }}
          </NButton>
        </div>
      </template>
    </NModal>

    <!-- 添加成员弹窗（org_admin）：单个 UUID + 批量 textarea，已在册由后端跳过 -->
    <NModal
      v-model:show="showAddMember"
      preset="card"
      style="width: 480px"
      :title="t('orgs.members.addTitle')"
    >
      <NForm label-placement="top">
        <NFormItem :label="t('orgs.members.userId')">
          <NInput
            v-model:value="addForm.userId"
            :placeholder="t('orgs.members.userIdPlaceholder')"
          />
        </NFormItem>
        <NFormItem :label="t('orgs.members.batchIds')">
          <NInput
            v-model:value="addForm.batch"
            type="textarea"
            :rows="4"
            :placeholder="t('orgs.members.batchPlaceholder')"
          />
        </NFormItem>
      </NForm>
      <template #footer>
        <div class="modal-actions">
          <NButton size="small" quaternary @click="showAddMember = false">
            {{ t('action.cancel') }}
          </NButton>
          <NButton size="small" type="primary" :loading="addingMember" @click="doAddMembers">
            {{ t('action.confirm') }}
          </NButton>
        </div>
      </template>
    </NModal>

    <!-- 创建团队弹窗（org_admin）：teams.org_id 固定为本组织 -->
    <NModal
      v-model:show="showCreateTeam"
      preset="card"
      style="width: 480px"
      :title="t('orgs.teams.createTitle')"
    >
      <NForm label-placement="top">
        <NFormItem :label="t('teams.create.name')" required>
          <NInput
            v-model:value="teamForm.name"
            maxlength="64"
            :placeholder="t('teams.create.namePlaceholder')"
          />
        </NFormItem>
        <NFormItem :label="t('teams.create.description')">
          <NInput
            v-model:value="teamForm.description"
            type="textarea"
            :rows="3"
            maxlength="2000"
            :placeholder="t('teams.create.descriptionPlaceholder')"
          />
        </NFormItem>
        <NFormItem :label="t('teams.settings.visibility')">
          <n-radio-group v-model:value="teamForm.visibility">
            <n-radio value="private">{{ t('teams.settings.visibilityPrivate') }}</n-radio>
            <n-radio value="public">{{ t('teams.settings.visibilityPublic') }}</n-radio>
          </n-radio-group>
        </NFormItem>
      </NForm>
      <template #footer>
        <div class="modal-actions">
          <NButton size="small" quaternary @click="showCreateTeam = false">
            {{ t('action.cancel') }}
          </NButton>
          <NButton size="small" type="primary" :loading="creatingTeam" @click="doCreateTeam">
            {{ t('action.save') }}
          </NButton>
        </div>
      </template>
    </NModal>

    <!-- 编辑信息抽屉（org_admin） -->
    <NDrawer v-model:show="showSettings" :width="440" placement="right">
      <NDrawerContent :title="t('orgs.settings.infoTitle')" closable>
        <NForm label-placement="top">
          <NFormItem :label="t('orgs.create.name')" required>
            <NInput v-model:value="form.name" maxlength="64" />
          </NFormItem>
          <NFormItem :label="t('orgs.create.description')">
            <NInput v-model:value="form.description" type="textarea" :rows="4" maxlength="2000" />
          </NFormItem>
          <NFormItem :label="t('orgs.settings.avatar')">
            <div class="avatar-uploader">
              <div class="avatar-preview" :class="{ empty: !form.avatar_url }">
                <img v-if="form.avatar_url" :src="form.avatar_url" alt="" />
                <span v-else>{{ t('orgs.settings.noAvatar') }}</span>
              </div>
              <label class="avatar-upload-btn">
                <input type="file" accept="image/*" hidden @change="onAvatarChange" />
                <NButton size="small" :loading="uploadingAvatar" tag="span">
                  {{ t('orgs.settings.avatar') }}
                </NButton>
              </label>
              <span class="field-hint">{{ t('contests.list.logoHint') }}</span>
            </div>
          </NFormItem>
        </NForm>
        <template #footer>
          <div class="modal-actions">
            <NButton @click="showSettings = false">{{ t('action.cancel') }}</NButton>
            <NButton type="primary" :loading="saving" @click="saveSettings">
              {{ t('action.save') }}
            </NButton>
          </div>
        </template>
      </NDrawerContent>
    </NDrawer>
  </WorkbenchShell>
</template>

<style scoped>
/* ============================================================
   通铺布局：抵消应用壳卡片默认 padding，内容直接铺满（同团队详情）
   ============================================================ */
.org-fill {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  margin: calc(-1 * var(--n-padding-top, 20px)) calc(-1 * var(--n-padding-left, 24px))
    calc(-1 * var(--n-padding-bottom, 24px));
}

/* ======== Hero：中性底，简洁单行 ======== */
.hero {
  position: relative;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 24px 32px 20px;
  border-bottom: 1px solid var(--app-border);
  background:
    radial-gradient(
      90% 220% at 97% 112%,
      color-mix(in srgb, var(--app-primary) 6%, transparent) 0%,
      transparent 62%
    ),
    radial-gradient(
      120% 180% at 0% 0%,
      color-mix(in srgb, var(--app-primary) 5%, transparent) 0%,
      transparent 52%
    ),
    var(--app-surface-muted, #f7f7fa);
  flex-wrap: wrap;
  overflow: hidden;
}
/* Hero 装饰（与团队工作台同款：圆弧 + 描边环，见 TeamDetailView） */
.hero__banner {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.hero__orb {
  position: absolute;
  width: 340px;
  height: 340px;
  border-radius: 999px;
  right: 7%;
  top: -252px;
  background: radial-gradient(
    circle at 50% 50%,
    color-mix(in srgb, var(--app-primary) 20%, transparent) 0%,
    color-mix(in srgb, var(--app-primary) 5%, transparent) 58%,
    transparent 74%
  );
}
.hero__ring {
  position: absolute;
  width: 228px;
  height: 228px;
  border-radius: 999px;
  right: -104px;
  bottom: -120px;
  border: 1px solid color-mix(in srgb, var(--app-primary) 24%, transparent);
}
.hero--skeleton {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: flex-start;
}
.hero--failed {
  padding: 48px 24px;
  display: flex;
  justify-content: center;
}
.hero__avatar {
  position: relative;
  border: 3px solid var(--app-card-bg, #fff);
  box-shadow: 0 2px 12px rgb(0 0 0 / 8%);
}
.hero__main {
  position: relative;
  flex: 1;
  min-width: 240px;
  display: grid;
  gap: 4px;
}
.hero__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.hero__title {
  margin: 0;
  line-height: 1.2;
  font-size: 22px;
  font-weight: 700;
  color: var(--app-text);
}
.hero__desc {
  margin: 0;
  color: var(--app-text);
  font-size: 13px;
  line-height: 1.6;
  max-width: 720px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.hero__desc--empty {
  color: var(--app-text-secondary);
  opacity: 0.6;
}
.hero__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--app-text-secondary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.hero__dot {
  opacity: 0.5;
}
.hero__meta-num {
  font-weight: 600;
  color: var(--app-text);
}
.hero__id {
  padding: 0;
  border: none;
  background: none;
  font: inherit;
  color: inherit;
  cursor: pointer;
  font-variant-numeric: tabular-nums;
  border-bottom: 1px dashed var(--app-border-strong);
  transition: color 0.15s ease;
}
.hero__id:hover {
  color: var(--app-primary);
}
.hero__actions {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-left: auto;
}

/* ======== 模块区：tab 线条直连内容，无卡片外框 ======== */
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
  padding: 4px 32px 0;
  flex-shrink: 0;
}
.module-tabs :deep(.n-tabs-tab) {
  font-size: 14px;
  padding: 12px 6px;
}
.module-tabs :deep(.n-tabs-pane-wrapper),
.module-tabs :deep(.n-tab-pane) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.module-tabs :deep(.n-tab-pane) {
  padding: 16px 32px 20px;
}

/* 表格单元格：头像 + 文本行内组合 */
.cell-user {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.cell-strong {
  font-weight: 600;
}
.cell-you {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 650;
  line-height: 1;
  padding: 2px 6px;
  border-radius: 999px;
  color: var(--app-primary);
  background: color-mix(in srgb, var(--app-primary) 12%, transparent);
}

/* 弹窗 / 抽屉底部动作区 */
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.field-hint {
  color: var(--app-text-secondary);
  font-size: 12px;
  margin: 0;
}

/* 头像上传（编辑抽屉，同团队设置） */
.avatar-uploader {
  display: flex;
  align-items: center;
  gap: 12px;
}
.avatar-preview {
  width: 56px;
  height: 56px;
  border-radius: 8px;
  border: 1px solid var(--app-border);
  display: grid;
  place-items: center;
  overflow: hidden;
  color: var(--app-text-secondary);
  font-size: 12px;
}
.avatar-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.avatar-upload-btn {
  cursor: pointer;
}

@media (max-width: 860px) {
  .hero {
    padding: 20px 16px;
  }
  .hero__actions {
    margin-left: 0;
    width: 100%;
  }
  .hero__avatar {
    width: 56px;
    height: 56px;
  }
  .module-tabs :deep(.n-tabs-nav),
  .module-tabs :deep(.n-tab-pane) {
    padding-left: 16px;
    padding-right: 16px;
  }
}
</style>
