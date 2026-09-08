<script setup lang="ts">
/**
 * 团队详情主页（/teams/:id）：社区空间式布局。
 * Hero（渐变横幅 + 头像 + 简介 + 动作区）+ 模块化内容区：
 * 成员 / 团队题库 / 团队题单 / 团队比赛 / 加入申请（管理员）。
 * 团队空间三模块（题库 / 题单 / 比赛）走独立团队端点（docs/contracts/teams.md 团队空间节）：
 * 成员只读浏览；创建者 / 管理员可引用题目题单、建题单、建比赛、编排与下线。
 * 邀请走弹窗（链接 + 二维码）；编辑走抽屉；权限按 my_role 显隐（creator ⊇ admin ⊇ member）。
 */
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { DataTableColumns } from 'naive-ui'
import {
  ArrowRight,
  CirclePlus,
  Collection,
  Document,
  MoreFilled,
  Promotion,
  Setting,
  Trophy,
} from '@element-plus/icons-vue'
import {
  NAvatar,
  NButton,
  NDropdown,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NForm,
  NFormItem,
  NIcon,
  NInput,
  NModal,
  NQrCode,
  NSkeleton,
  NSpin,
  NTag,
} from 'naive-ui'

import {
  archiveTeamProblemSet,
  createTeamInvite,
  disbandTeam,
  exitTeam,
  getTeam,
  kickTeamMember,
  listTeamApplications,
  listTeamContests,
  listTeamMembers,
  listTeamProblemSets,
  listTeamProblems,
  replaceTeamProblemSetItems,
  reviewTeamApplication,
  searchTeamArrangeableProblems,
  setTeamAdmin,
  updateTeam,
} from '@/api/teams'
import { uploadImage } from '@/api/files'
import { archiveProblem } from '@/api/problems'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { formatDateTime } from '@/utils/format'
import { useUserStore } from '@/stores/user'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import type {
  ContestSummary,
  ProblemSetSummary,
  TeamApplicationItem,
  TeamDetail,
  TeamMemberItem,
  TeamProblemSummary,
} from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const teamId = String(route.params.id)
const team = ref<TeamDetail | null>(null)
const loadFailed = ref(false)
const loading = ref(false)

const isCreator = computed(() => team.value?.my_role === 'creator')
const isAdmin = computed(() => team.value?.my_role === 'creator' || team.value?.my_role === 'admin')

function initialOf(name: string | null | undefined) {
  return name?.trim()?.charAt(0).toUpperCase() || 'T'
}

// ---------------- 模块 tab（内容板块） ----------------

type TeamModule = 'members' | 'problems' | 'sets' | 'contests' | 'applications'
const activeModule = ref<TeamModule>('members')

const moduleMeta = computed(() => {
  const items: Array<{
    key: TeamModule
    labelKey: string
    icon: typeof Collection
    adminOnly?: boolean
  }> = [
    { key: 'members', labelKey: 'teams.detail.tabMembers', icon: Setting },
    { key: 'problems', labelKey: 'teams.modules.problems', icon: Collection },
    { key: 'sets', labelKey: 'teams.modules.sets', icon: Document },
    { key: 'contests', labelKey: 'teams.modules.contests', icon: Trophy },
    {
      key: 'applications',
      labelKey: 'teams.detail.tabApplications',
      icon: Promotion,
      adminOnly: true,
    },
  ]
  return items.filter((item) => !item.adminOnly || isAdmin.value)
})

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
} = usePagination({ defaultPageSize: 10 })

async function loadProblems() {
  problemsLoading.value = true
  try {
    const result = await listTeamProblems(teamId, {
      page: problemPage.value,
      page_size: problemPageSize.value,
      keyword: problemKeyword.value || undefined,
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

function openTeamProblem(row: TeamProblemSummary) {
  void router.push(`/teams/${teamId}/problems/${row.id}`)
}

/** 题库行内操作（⋯ 下拉，仅团队管理可见；backend 仍强校验 owner/admin） */
type ProblemAction = 'edit' | 'archive'

function problemActions(row: TeamProblemSummary): Array<{ key: ProblemAction; label: string }> {
  const actions: Array<{ key: ProblemAction; label: string }> = [
    { key: 'edit', label: t('action.edit') },
  ]
  if (row.status === 'published') {
    actions.push({ key: 'archive', label: t('problems.detail.archive') })
  }
  return actions
}

function onProblemAction(key: ProblemAction, row: TeamProblemSummary) {
  if (key === 'edit') {
    void router.push(`/teams/${teamId}/problems/${row.id}/edit/statement`)
    return
  }
  confirmAsyncDialog({
    title: t('problems.detail.archive'),
    content: t('problems.mine.archiveConfirm'),
    positiveText: t('problems.detail.archive'),
    action: async () => {
      await archiveProblem(row.id)
    },
    successMessage: t('problems.detail.archiveSuccess'),
    onAfterSuccess: () => loadProblems(),
  })
}

/** 引用题目页（团队题目 = 引用制）：tutor / admin 全局身份才拥有可引用的本人题目 */
const canReference = computed(() => userStore.hasAnyRole(['admin', 'tutor']))

function openProblemReference() {
  void router.push(`/teams/${teamId}/problems/new`)
}

/** 团队题目直建向导（POST /problems 带 team_id，团队可见性分支） */
function openProblemCreate() {
  void router.push(`/teams/${teamId}/problems/create`)
}

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
} = usePagination({ defaultPageSize: 10 })

async function loadSets() {
  setsLoading.value = true
  try {
    const result = await listTeamProblemSets(teamId, {
      page: setPage.value,
      page_size: setPageSize.value,
      keyword: setKeyword.value || undefined,
    })
    sets.value = result.items
    setTotal.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    setsLoading.value = false
  }
}

/** 新建 / 引用收敛到题单创建页（引用 tab 仅 tutor / admin 可见） */
function openSetCreate() {
  void router.push(`/teams/${teamId}/sets/new`)
}

/** 团队题库列表列（行点击进团队写题页；限制 + 通过率） */
const problemColumns = computed<DataTableColumns<TeamProblemSummary>>(() => [
  {
    title: t('problems.list.name'),
    key: 'title',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'cell-strong' }, row.title),
  },
  {
    title: t('problems.list.difficulty'),
    key: 'difficulty',
    width: 80,
    align: 'center',
    render: (row) => ((row.difficulty ?? null) === null ? '--' : String(row.difficulty)),
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
    render(row) {
      const total = row.submission_count ?? 0
      if (!total) return '--'
      const accepted = row.accepted_count ?? 0
      return `${accepted}/${total}`
    },
  },
  ...(isAdmin.value
    ? [
        {
          title: '',
          key: 'ops',
          width: 48,
          render: (row: TeamProblemSummary) =>
            h(
              NDropdown,
              {
                trigger: 'click',
                options: problemActions(row).map((a) => ({ key: a.key, label: a.label })),
                onSelect: (key: ProblemAction) => onProblemAction(key, row),
              },
              {
                default: () =>
                  h(
                    NButton,
                    {
                      circle: true,
                      quaternary: true,
                      size: 'tiny',
                      'aria-label': t('teams.detail.more'),
                      // 阻断冒泡：行 onClick 会把点击吞成「进入题目」
                      onClick: (e: MouseEvent) => e.stopPropagation(),
                    },
                    { icon: () => h(NIcon, { component: MoreFilled }) },
                  ),
              },
            ),
        },
      ]
    : []),
])

function rowKeyOfProblem(row: TeamProblemSummary) {
  return row.id
}

function rowPropsOfProblem(row: TeamProblemSummary) {
  return {
    style: 'cursor: pointer;',
    onClick: () => openTeamProblem(row),
  }
}

/** 团队题单列表列（行点击进团队题单详情；编排 / 下线收敛在 ⋯ 下拉） */
const setColumns = computed<DataTableColumns<ProblemSetSummary>>(() => [
  {
    title: t('problemSets.list.titleLabel'),
    key: 'title',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'cell-strong' }, row.title),
  },
  {
    title: t('admin.teams.setVisible'),
    key: 'item_count',
    width: 80,
    align: 'center',
    render: (row) => String(row.item_count),
  },
  {
    title: t('problemSets.list.status'),
    key: 'status',
    width: 88,
    render(row) {
      const active = row.status === 'active'
      return h(
        NTag,
        { size: 'small', bordered: false, type: active ? 'info' : 'warning' },
        { default: () => t(active ? 'problemSets.list.active' : 'problemSets.detail.archived') },
      )
    },
  },
  ...(isAdmin.value
    ? [
        {
          title: '',
          key: 'ops',
          width: 48,
          render: (row: ProblemSetSummary) =>
            h(
              NDropdown,
              {
                trigger: 'click',
                options: setActions(row).map((a) => ({ key: a.key, label: a.label })),
                onSelect: (key: SetAction) => onSetAction(key, row),
              },
              {
                default: () =>
                  h(
                    NButton,
                    {
                      circle: true,
                      quaternary: true,
                      size: 'tiny',
                      'aria-label': t('teams.detail.more'),
                      // 阻断冒泡：行 onClick 会把点击吞成「进入题单详情」
                      onClick: (e: MouseEvent) => e.stopPropagation(),
                    },
                    { icon: () => h(NIcon, { component: MoreFilled }) },
                  ),
              },
            ),
        },
      ]
    : []),
])

function rowKeyOfSet(row: ProblemSetSummary) {
  return row.id
}

function rowPropsOfSet(row: ProblemSetSummary) {
  return {
    style: 'cursor: pointer;',
    onClick: () => router.push(`/teams/${teamId}/sets/${row.id}`),
  }
}

async function onArchiveSet(row: ProblemSetSummary) {
  confirmAsyncDialog({
    title: t('teams.space.archiveSet'),
    content: t('teams.space.archiveSetConfirm', { title: row.title }),
    positiveText: t('teams.space.archiveSet'),
    action: async () => {
      await archiveTeamProblemSet(teamId, row.id)
    },
    successMessage: t('teams.space.setArchived'),
    onAfterSuccess: () => {
      loadSets()
    },
  })
}

/** 题单行内操作（⋯ 下拉，仅团队管理可见）：编排 / 下线 */
type SetAction = 'arrange' | 'archive'

function setActions(row: ProblemSetSummary): Array<{ key: SetAction; label: string }> {
  const actions: Array<{ key: SetAction; label: string }> = [
    { key: 'arrange', label: t('teams.space.arrange') },
  ]
  if (row.status === 'active') {
    actions.push({ key: 'archive', label: t('teams.space.archiveSet') })
  }
  return actions
}

function onSetAction(key: SetAction, row: ProblemSetSummary) {
  if (key === 'arrange') {
    void openArrange(row)
    return
  }
  void onArchiveSet(row)
}

/** 编排团队题单弹窗（ProblemPicker 换团队编排候选源） */
const arrangingSet = ref<ProblemSetSummary | null>(null)
const arrangingItems = ref<Array<{ problem_id: string; sort_order: number }>>([])
const arrangingSource = ref<TeamProblemSummary[]>([])
const arrangingKeyword = ref('')
const arrangeSearchLoading = ref(false)
const savingArrange = ref(false)

async function openArrange(row: ProblemSetSummary) {
  arrangingSet.value = row
  arrangingKeyword.value = ''
  arrangingItems.value = []
  void searchArrangeable()
  // 取该题单当前条目（题单详情端点对团队成员可见）以预填
  try {
    const { getProblemSet } = await import('@/api/problemSets')
    const d = await getProblemSet(row.id)
    arrangingItems.value = d.items.map((it) => ({
      problem_id: it.problem_id,
      sort_order: it.sort_order,
    }))
  } catch {
    /* 预填失败不阻塞弹窗 */
  }
}

async function searchArrangeable() {
  arrangeSearchLoading.value = true
  try {
    const result = await searchTeamArrangeableProblems(teamId, {
      keyword: arrangingKeyword.value || undefined,
      page: 1,
      page_size: 50,
    })
    arrangingSource.value = result.items
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    arrangeSearchLoading.value = false
  }
}

function addArrangeItem(problem: TeamProblemSummary) {
  if (arrangingItems.value.some((it) => it.problem_id === problem.id)) return
  arrangingItems.value.push({ problem_id: problem.id, sort_order: arrangingItems.value.length })
}

function removeArrangeItem(problemId: string) {
  arrangingItems.value = arrangingItems.value.filter((it) => it.problem_id !== problemId)
}

const arrangingTitles = computed(() => {
  const map = new Map<string, string>()
  arrangingSource.value.forEach((p) => map.set(p.id, p.title))
  return map
})

async function saveArrange() {
  if (!arrangingSet.value) return
  savingArrange.value = true
  try {
    await replaceTeamProblemSetItems(teamId, arrangingSet.value.id, {
      items: arrangingItems.value.map((it, index) => ({
        problem_id: it.problem_id,
        sort_order: index,
      })),
    })
    message.success(t('teams.space.arranged'))
    arrangingSet.value = null
    loadSets()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    savingArrange.value = false
  }
}

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
} = usePagination({ defaultPageSize: 10 })

async function loadContests() {
  contestsLoading.value = true
  try {
    const result = await listTeamContests(teamId, {
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

function openContest(row: ContestSummary) {
  // 限界上下文：留在团队路由前缀内（frontend.md 路由上下文隔离）
  void router.push(`/teams/${teamId}/contests/${row.id}`)
}

function searchContests() {
  resetContestPage()
  loadContests()
}

/** 创建团队比赛 → 独立创建页（题目编排随后在比赛编辑页进行） */
function openContestCreate() {
  void router.push(`/teams/${teamId}/contests/new`)
}

// ---------------- 团队信息 ----------------

async function load() {
  loading.value = true
  try {
    team.value = await getTeam(teamId)
    loadFailed.value = false
  } catch (error) {
    loadFailed.value = true
    message.error(error instanceof Error ? error.message : t('teams.detail.loadFailed'))
  } finally {
    loading.value = false
  }
}

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
} = usePagination({ defaultPageSize: 10 })

async function loadMembers() {
  membersLoading.value = true
  try {
    const result = await listTeamMembers(teamId, {
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

function searchSets() {
  resetSetPage()
  loadSets()
}

/** 成员行操作（⋯ 下拉）：设 / 撤管理员（仅创建者）、移出（管理员） */
type MemberAction = 'grant' | 'revoke' | 'kick'

function memberActions(row: TeamMemberItem): Array<{ key: MemberAction; label: string }> {
  const actions: Array<{ key: MemberAction; label: string }> = []
  if (isCreator.value && !row.is_creator) {
    actions.push({
      key: row.is_admin ? 'revoke' : 'grant',
      label: t(row.is_admin ? 'teams.members.revokeAdmin' : 'teams.members.grantAdmin'),
    })
  }
  if (isAdmin.value && !row.is_creator) {
    actions.push({ key: 'kick', label: t('teams.members.kick') })
  }
  return actions
}

function onMemberAction(action: MemberAction, row: TeamMemberItem) {
  if (action === 'grant' || action === 'revoke') {
    void onSetAdmin(row, action === 'grant')
    return
  }
  onKick(row)
}

async function onSetAdmin(row: TeamMemberItem, grant: boolean) {
  try {
    await setTeamAdmin(teamId, row.user_id, grant)
    message.success(t(grant ? 'teams.members.grantSuccess' : 'teams.members.revokeSuccess'))
    await loadMembers()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

function onKick(row: TeamMemberItem) {
  confirmAsyncDialog({
    title: t('teams.members.kick'),
    content: t('teams.members.kickConfirm', { name: row.nickname }),
    positiveText: t('teams.members.kick'),
    action: async () => {
      await kickTeamMember(teamId, row.user_id)
    },
    successMessage: t('teams.members.kickSuccess'),
    onAfterSuccess: () => {
      loadMembers()
      load()
    },
  })
}

// ---------------- 加入申请 ----------------

const applications = ref<TeamApplicationItem[]>([])
const applicationsLoading = ref(false)

async function loadApplications() {
  if (!isAdmin.value) return
  applicationsLoading.value = true
  try {
    const result = await listTeamApplications(teamId, { page: 1, page_size: 50 })
    applications.value = result.items
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    applicationsLoading.value = false
  }
}

async function onReview(row: TeamApplicationItem, approve: boolean) {
  try {
    await reviewTeamApplication(teamId, row.id, approve)
    message.success(
      t(approve ? 'teams.applications.approveSuccess' : 'teams.applications.rejectSuccess'),
    )
    await Promise.all([loadApplications(), loadMembers(), load()])
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

// ---------------- 邀请（弹窗：链接 + 二维码） ----------------

const invite = reactive({ token: '', expiresAt: '' as string, show: false })
const inviting = ref(false)

async function onCreateInvite() {
  inviting.value = true
  try {
    const result = await createTeamInvite(teamId)
    invite.token = result.token
    invite.expiresAt = formatDateTime(result.expires_at)
    invite.show = true
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    inviting.value = false
  }
}

const inviteLink = computed(() =>
  invite.token ? `${window.location.origin}/teams/invites/${invite.token}` : '',
)

/** 复制团队 ID（统计行）：显示前 8 位，复制完整 ID */
async function copyTeamId() {
  try {
    await navigator.clipboard.writeText(teamId)
    message.success(t('problems.detail.copied'))
  } catch {
    message.error(t('common.operationFailed'))
  }
}

async function copyInviteLink() {
  try {
    await navigator.clipboard.writeText(inviteLink.value)
    message.success(t('problems.detail.copied'))
  } catch {
    message.error(t('common.operationFailed'))
  }
}

// ---------------- 编辑抽屉 ----------------

const showSettings = ref(false)
const form = reactive({ name: '', description: '', avatar_url: '' as string | null })
const saving = ref(false)
const uploadingAvatar = ref(false)

function openSettings() {
  if (!team.value) return
  form.name = team.value.name
  form.description = team.value.description ?? ''
  form.avatar_url = team.value.avatar_url ?? ''
  showSettings.value = true
}

async function onAvatarChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploadingAvatar.value = true
  try {
    const result = await uploadImage(file)
    form.avatar_url = result.url
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.imageUploadFailed'))
  } finally {
    uploadingAvatar.value = false
    input.value = ''
  }
}

async function saveSettings() {
  if (!form.name.trim()) {
    message.warning(t('teams.create.nameRequired'))
    return
  }
  saving.value = true
  try {
    team.value = await updateTeam(teamId, {
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      avatar_url: form.avatar_url || undefined,
    })
    message.success(t('teams.settings.saved'))
    showSettings.value = false
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    saving.value = false
  }
}

// ---------------- 退出 / 解散（更多下拉） ----------------

type HeroAction = 'exit' | 'disband'

const heroActions = computed(() => {
  const actions: Array<{ key: HeroAction; label: string }> = []
  if (!isCreator.value) actions.push({ key: 'exit', label: t('teams.detail.exit') })
  if (isCreator.value) actions.push({ key: 'disband', label: t('teams.detail.disband') })
  return actions
})

function onHeroAction(key: HeroAction) {
  if (key === 'exit') onExit()
  else onDisband()
}

function onExit() {
  confirmAsyncDialog({
    title: t('teams.detail.exit'),
    content: t('teams.detail.exitConfirm'),
    positiveText: t('teams.detail.exit'),
    action: async () => {
      await exitTeam(teamId)
    },
    successMessage: t('teams.detail.exitSuccess'),
    onAfterSuccess: () => {
      void router.push('/teams/mine')
    },
  })
}

function onDisband() {
  confirmAsyncDialog({
    title: t('teams.detail.disband'),
    content: t('teams.detail.disbandConfirm'),
    positiveText: t('teams.detail.disband'),
    action: async () => {
      await disbandTeam(teamId)
    },
    successMessage: t('teams.detail.disbandSuccess'),
    onAfterSuccess: () => {
      void router.push('/teams/mine')
    },
  })
}

// ---------------- 初始化 ----------------

watch(
  () => team.value?.id,
  () => {
    if (team.value) {
      loadMembers()
      loadApplications()
      loadProblems()
      loadSets()
      loadContests()
    }
  },
)

onMounted(load)
</script>

<template>
  <WorkbenchShell>
    <div class="team-fill">
      <!-- NSpin 只包 Hero（骨架 / 失败 / 信息），不参与模块卡的高度传导 -->
      <NSpin :show="loading" class="hero-spin">
        <!-- 加载骨架 -->
        <div v-if="!team && loading" class="hero hero--skeleton">
          <NSkeleton height="140px" :sharp="false" style="border-radius: 8px" />
          <NSkeleton
            circle
            width="88px"
            height="88px"
            class="hero__avatar hero__avatar--skeleton"
          />
          <NSkeleton text style="width: 30%" />
          <NSkeleton text style="width: 60%" />
        </div>

        <!-- 加载失败 -->
        <div v-else-if="!team && loadFailed" class="hero hero--failed">
          <NEmpty :description="t('teams.detail.loadFailed')" size="large">
            <template #extra>
              <NButton @click="load">{{ t('action.refresh') }}</NButton>
            </template>
          </NEmpty>
        </div>
      </NSpin>

      <!-- ======== Hero（不参与模块卡高度链） ======== -->
      <section v-if="team" class="hero">
        <div class="hero__banner" aria-hidden="true">
          <span class="hero__orb"></span>
          <span class="hero__ring"></span>
        </div>
        <div class="hero__body">
          <img v-if="team.avatar_url" :src="team.avatar_url" alt="" class="hero__avatar" />
          <div v-else class="hero__avatar hero__avatar--fallback" aria-hidden="true">
            {{ initialOf(team.name) }}
          </div>

          <div class="hero__main">
            <div class="hero__title-row">
              <h1 class="hero__title">{{ team.name }}</h1>
            </div>
            <p class="hero__desc" :class="{ 'hero__desc--empty': !team.description }">
              {{ team.description ?? t('teams.detail.descEmpty') }}
            </p>
            <!-- 统计行：成员数 / 创建时间 / 团队 ID（点击复制完整 ID） -->
            <div class="hero__meta">
              <span>
                {{ t('teams.list.memberCount') }}
                <strong class="hero__meta-num">{{ team.member_count }}</strong>
              </span>
              <span class="hero__dot" aria-hidden="true">·</span>
              <span>{{ t('teams.list.createdAt') }} {{ formatDateTime(team.created_at) }}</span>
              <span class="hero__dot" aria-hidden="true">·</span>
              <button
                type="button"
                class="hero__id"
                :title="t('teams.detail.teamId')"
                @click="copyTeamId"
              >
                {{ t('teams.detail.teamId') }} {{ teamId.slice(0, 8) }}
              </button>
            </div>
          </div>

          <!-- 动作区：预留扩展位，后续团队管理按钮继续向此追加 -->
          <div class="hero__actions">
            <NButton
              v-if="isAdmin"
              type="primary"
              size="large"
              :loading="inviting"
              @click="onCreateInvite"
            >
              <template #icon>
                <NIcon :component="Promotion" />
              </template>
              {{ t('teams.detail.inviteMembers') }}
            </NButton>
            <NButton v-if="isAdmin" secondary size="large" @click="openSettings">
              <template #icon>
                <NIcon :component="Setting" />
              </template>
              {{ t('teams.detail.editInfo') }}
            </NButton>
            <NDropdown
              v-if="heroActions.length"
              trigger="click"
              :options="heroActions"
              @select="onHeroAction"
            >
              <NButton circle quaternary size="large" :aria-label="t('teams.detail.more')">
                <template #icon>
                  <NIcon :component="MoreFilled" />
                </template>
              </NButton>
            </NDropdown>
          </div>
        </div>
      </section>

      <!-- ======== 内容模块（tab 线条直连内容） ======== -->
      <section v-if="team" class="module-area">
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
                :placeholder="t('teams.members.search')"
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
              <div class="pane-scroll">
                <NSpin :show="membersLoading" class="pane-spin">
                  <ul v-if="members.length" class="member-grid">
                    <li v-for="member in members" :key="member.user_id" class="member-cell">
                      <NAvatar
                        :src="member.avatar_url || undefined"
                        round
                        :size="44"
                        :style="{
                          color: 'var(--app-text-secondary)',
                          fontSize: '15px',
                          flexShrink: 0,
                        }"
                      >
                        <template v-if="!member.avatar_url">{{
                          initialOf(member.nickname)
                        }}</template>
                      </NAvatar>
                      <div class="member-cell__main">
                        <span class="member-cell__name" :title="member.nickname">
                          {{ member.nickname }}
                        </span>
                        <span class="member-cell__time">
                          {{ t('teams.members.joinedAt') }} {{ formatDateTime(member.joined_at) }}
                        </span>
                      </div>
                      <NTag
                        size="small"
                        round
                        :bordered="false"
                        :type="member.is_creator ? 'warning' : member.is_admin ? 'info' : 'default'"
                        class="member-cell__role"
                      >
                        {{
                          member.is_creator
                            ? t('teams.role.creator')
                            : member.is_admin
                              ? t('teams.role.admin')
                              : t('teams.role.member')
                        }}
                      </NTag>
                      <NDropdown
                        v-if="memberActions(member).length"
                        class="member-cell__ops"
                        trigger="click"
                        :options="memberActions(member)"
                        @select="(action: MemberAction) => onMemberAction(action, member)"
                      >
                        <NButton circle quaternary size="tiny" :aria-label="t('teams.detail.more')">
                          <template #icon>
                            <NIcon :component="MoreFilled" />
                          </template>
                        </NButton>
                      </NDropdown>
                    </li>
                  </ul>
                  <NEmpty
                    v-else-if="!membersLoading"
                    :description="t('teams.members.empty')"
                    size="large"
                    class="pane-empty"
                  />
                </NSpin>
              </div>

              <div class="pane-pager">
                <span class="pane-pager__total">
                  {{ t('teams.pane.memberTotal', { count: memberTotal }) }}
                </span>
                <n-pagination
                  :page="memberPage"
                  :page-size="memberPageSize"
                  :item-count="memberTotal"
                  :page-sizes="[10, 20, 50]"
                  show-size-picker
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
              </div>
            </template>

            <!-- 团队题库 -->
            <template v-else-if="moduleItem.key === 'problems'">
              <SearchFilterBar
                :keyword="problemKeyword"
                :placeholder="t('teams.space.problemSearch')"
                @update:keyword="
                  (v: string) => {
                    problemKeyword = v
                  }
                "
                @search="searchProblems"
                @reset="searchProblems"
              >
                <template #actions>
                  <NButton v-if="isAdmin" size="small" secondary @click="openProblemCreate">
                    <template #icon>
                      <NIcon :component="Collection" />
                    </template>
                    {{ t('problems.create.title') }}
                  </NButton>
                  <NButton
                    v-if="isAdmin && canReference"
                    size="small"
                    type="primary"
                    secondary
                    @click="openProblemReference"
                  >
                    <template #icon>
                      <NIcon :component="CirclePlus" />
                    </template>
                    {{ t('teams.space.referenceProblem') }}
                  </NButton>
                  <RefreshButton
                    :loading="problemsLoading"
                    :aria-label="t('action.refresh')"
                    @click="loadProblems"
                  />
                </template>
              </SearchFilterBar>
              <div class="pane-scroll">
                <n-data-table
                  v-show="problems.length || problemsLoading"
                  size="small"
                  class="pane-table"
                  :columns="problemColumns"
                  :data="problems"
                  :loading="problemsLoading"
                  :bordered="false"
                  :bottom-bordered="false"
                  :row-key="rowKeyOfProblem"
                  :row-props="rowPropsOfProblem"
                />
                <div
                  v-show="!problems.length && !problemsLoading"
                  class="table-fill-empty pane-empty"
                >
                  <NEmpty :description="t('teams.space.problemsEmpty')" size="large" />
                </div>
              </div>
              <div class="pane-pager">
                <span class="pane-pager__total">
                  {{ t('teams.pane.problemTotal', { count: problemTotal }) }}
                </span>
                <n-pagination
                  :page="problemPage"
                  :page-size="problemPageSize"
                  :item-count="problemTotal"
                  :page-sizes="[10, 20, 50]"
                  show-size-picker
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
              </div>
            </template>

            <!-- 团队题单 -->
            <template v-else-if="moduleItem.key === 'sets'">
              <SearchFilterBar
                :keyword="setKeyword"
                :placeholder="t('problemSets.list.search')"
                @update:keyword="
                  (v: string) => {
                    setKeyword = v
                  }
                "
                @search="searchSets"
                @reset="searchSets"
              >
                <template #actions>
                  <NButton v-if="isAdmin" size="small" type="primary" @click="openSetCreate">
                    <template #icon>
                      <NIcon :component="CirclePlus" />
                    </template>
                    {{ t('teams.space.createSet') }}
                  </NButton>
                  <RefreshButton
                    :loading="setsLoading"
                    :aria-label="t('action.refresh')"
                    @click="loadSets"
                  />
                </template>
              </SearchFilterBar>
              <div class="pane-scroll">
                <n-data-table
                  v-show="sets.length || setsLoading"
                  size="small"
                  class="pane-table"
                  :columns="setColumns"
                  :data="sets"
                  :loading="setsLoading"
                  :bordered="false"
                  :bottom-bordered="false"
                  :row-key="rowKeyOfSet"
                  :row-props="rowPropsOfSet"
                />
                <div v-show="!sets.length && !setsLoading" class="table-fill-empty pane-empty">
                  <NEmpty :description="t('teams.space.setsEmpty')" size="large" />
                </div>
              </div>
              <div class="pane-pager">
                <span class="pane-pager__total">
                  {{ t('teams.pane.setTotal', { count: setTotal }) }}
                </span>
                <n-pagination
                  :page="setPage"
                  :page-size="setPageSize"
                  :item-count="setTotal"
                  :page-sizes="[10, 20, 50]"
                  show-size-picker
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
              </div>
            </template>

            <!-- 团队比赛 -->
            <template v-else-if="moduleItem.key === 'contests'">
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
              <div class="pane-scroll">
                <NSpin :show="contestsLoading" class="pane-spin">
                  <ul v-if="contests.length" class="member-grid">
                    <li
                      v-for="contest in contests"
                      :key="contest.id"
                      class="member-cell member-cell--link"
                      role="button"
                      tabindex="0"
                      @click="openContest(contest)"
                      @keyup.enter="openContest(contest)"
                    >
                      <span class="member-cell__avatar-text" aria-hidden="true">C</span>
                      <div class="member-cell__main">
                        <span class="member-cell__name" :title="contest.title">{{
                          contest.title
                        }}</span>
                        <span class="member-cell__time">
                          {{ formatDateTime(contest.start_time) }} →
                          {{ formatDateTime(contest.end_time) }}
                        </span>
                      </div>
                      <NTag
                        size="small"
                        round
                        :bordered="false"
                        :type="
                          contest.status === 'running'
                            ? 'success'
                            : contest.status === 'scheduled'
                              ? 'info'
                              : 'default'
                        "
                        class="member-cell__role"
                      >
                        {{
                          t(
                            contest.status === 'running'
                              ? 'contests.statusRunning'
                              : contest.status === 'scheduled'
                                ? 'contests.statusScheduled'
                                : 'contests.statusFinished',
                          )
                        }}
                      </NTag>
                      <NIcon class="member-cell__arrow" :component="ArrowRight" />
                    </li>
                  </ul>
                  <NEmpty
                    v-else-if="!contestsLoading"
                    :description="t('teams.space.contestsEmpty')"
                    size="large"
                    class="pane-empty"
                  />
                </NSpin>
              </div>
              <div class="pane-pager">
                <span class="pane-pager__total">
                  {{ t('teams.pane.contestTotal', { count: contestTotal }) }}
                </span>
                <n-pagination
                  :page="contestPage"
                  :page-size="contestPageSize"
                  :item-count="contestTotal"
                  :page-sizes="[10, 20, 50]"
                  show-size-picker
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
              </div>
            </template>

            <!-- 加入申请（管理员） -->
            <template v-else>
              <div class="pane-scroll">
                <NSpin :show="applicationsLoading" class="pane-spin">
                  <ul v-if="applications.length" class="member-grid">
                    <li
                      v-for="application in applications"
                      :key="application.id"
                      class="member-cell"
                    >
                      <NAvatar
                        round
                        :size="44"
                        :style="{
                          color: 'var(--app-text-secondary)',
                          fontSize: '15px',
                          flexShrink: 0,
                        }"
                      >
                        {{ initialOf(application.nickname) }}
                      </NAvatar>
                      <div class="member-cell__main">
                        <span class="member-cell__name" :title="application.nickname">
                          {{ application.nickname }}
                        </span>
                        <span class="member-cell__time">
                          {{ formatDateTime(application.applied_at) }}
                        </span>
                      </div>
                      <NTag
                        size="small"
                        round
                        :bordered="false"
                        :type="application.invite_token ? 'info' : 'default'"
                        class="member-cell__role"
                      >
                        {{
                          application.invite_token
                            ? t('teams.applications.viaInvite')
                            : t('teams.applications.direct')
                        }}
                      </NTag>
                      <div class="member-cell__actions">
                        <NButton size="small" type="primary" @click="onReview(application, true)">
                          {{ t('teams.applications.approve') }}
                        </NButton>
                        <NButton
                          size="small"
                          quaternary
                          type="error"
                          @click="onReview(application, false)"
                        >
                          {{ t('teams.applications.reject') }}
                        </NButton>
                      </div>
                    </li>
                  </ul>
                  <NEmpty
                    v-else-if="!applicationsLoading"
                    :description="t('teams.applications.empty')"
                    size="large"
                    class="pane-empty"
                  />
                </NSpin>
              </div>
            </template>
          </n-tab-pane>
        </n-tabs>
      </section>
    </div>

    <!-- 邀请弹窗：二维码 + 链接 -->
    <NModal
      v-model:show="invite.show"
      preset="card"
      style="width: 440px"
      :title="t('teams.settings.inviteTitle')"
    >
      <div class="invite-modal">
        <div class="invite-modal__qr">
          <!-- padding=0：组件默认 12px 内边距在 border-box 下会挤压画布，
               右下约 24px 被容器 overflow:hidden 裁掉；留白改由外层承担 -->
          <NQrCode
            v-if="inviteLink"
            :value="inviteLink"
            :size="176"
            :padding="0"
            error-correction-level="M"
          />
        </div>
        <p class="invite-modal__hint">{{ t('teams.settings.inviteHint') }}</p>
        <div class="invite-modal__link">
          <span class="invite-modal__url" :title="inviteLink">{{ inviteLink }}</span>
          <div class="invite-modal__actions">
            <NButton size="small" type="primary" secondary @click="copyInviteLink">
              {{ t('action.copyLink') }}
            </NButton>
            <NButton size="small" quaternary :loading="inviting" @click="onCreateInvite">
              {{ t('teams.settings.regenerate') }}
            </NButton>
          </div>
        </div>
        <p class="field-hint">
          {{ t('teams.settings.inviteExpiry', { time: invite.expiresAt }) }}
        </p>
      </div>
    </NModal>

    <!-- 编辑信息抽屉 -->
    <NDrawer v-model:show="showSettings" :width="440" placement="right">
      <NDrawerContent :title="t('teams.settings.infoTitle')" closable>
        <NForm label-placement="top">
          <NFormItem :label="t('teams.create.name')" required>
            <NInput v-model:value="form.name" maxlength="64" />
          </NFormItem>
          <NFormItem :label="t('teams.create.description')">
            <NInput v-model:value="form.description" type="textarea" :rows="4" maxlength="2000" />
          </NFormItem>
          <NFormItem :label="t('teams.settings.avatar')">
            <div class="avatar-uploader">
              <div class="avatar-preview" :class="{ empty: !form.avatar_url }">
                <img v-if="form.avatar_url" :src="form.avatar_url" alt="" />
                <span v-else>{{ t('teams.settings.noAvatar') }}</span>
              </div>
              <label class="avatar-upload-btn">
                <input type="file" accept="image/*" hidden @change="onAvatarChange" />
                <NButton size="small" :loading="uploadingAvatar" tag="span">
                  {{ t('teams.settings.avatar') }}
                </NButton>
              </label>
              <span class="field-hint">{{ t('contests.list.logoHint') }}</span>
            </div>
          </NFormItem>
        </NForm>
        <template #footer>
          <div class="drawer-footer">
            <NButton @click="showSettings = false">{{ t('action.cancel') }}</NButton>
            <NButton type="primary" :loading="saving" @click="saveSettings">
              {{ t('action.save') }}
            </NButton>
          </div>
        </template>
      </NDrawerContent>
    </NDrawer>

    <!-- 编排团队题单 -->
    <NModal
      :show="Boolean(arrangingSet)"
      preset="card"
      style="width: min(760px, 94vw)"
      :title="t('teams.space.arrangeTitle', { title: arrangingSet?.title ?? '' })"
      @update:show="
        (v: boolean) => {
          if (!v) arrangingSet = null
        }
      "
    >
      <div class="arrange">
        <div class="arrange__picker">
          <div class="reference-picker__bar">
            <NInput
              v-model:value="arrangingKeyword"
              clearable
              size="small"
              style="max-width: 260px"
              :placeholder="t('teams.space.problemSearch')"
              @keyup.enter="searchArrangeable"
              @clear="searchArrangeable"
            />
            <NButton
              size="small"
              secondary
              :loading="arrangeSearchLoading"
              @click="searchArrangeable"
            >
              {{ t('action.search') }}
            </NButton>
          </div>
          <ul v-if="arrangingSource.length" class="reference-picker__list arrange__source">
            <li v-for="p in arrangingSource" :key="p.id" class="reference-picker__item">
              <span class="reference-picker__title" :title="p.title">{{ p.title }}</span>
              <span class="reference-picker__meta">
                {{ t('problems.list.limits') }} {{ p.time_limit_ms }}ms / {{ p.memory_limit_mb }}MB
              </span>
              <NButton
                size="tiny"
                type="primary"
                secondary
                :disabled="arrangingItems.some((it) => it.problem_id === p.id)"
                @click="addArrangeItem(p)"
              >
                {{ t('problemSets.detail.add') }}
              </NButton>
            </li>
          </ul>
          <NEmpty
            v-else-if="!arrangeSearchLoading"
            :description="t('teams.space.noArrangeable')"
            size="small"
          />
        </div>
        <div class="arrange__chosen">
          <p class="arrange__label">
            {{ t('teams.space.chosenCount', { count: arrangingItems.length }) }}
          </p>
          <ul class="reference-picker__list arrange__list">
            <li
              v-for="(item, index) in arrangingItems"
              :key="item.problem_id"
              class="reference-picker__item"
            >
              <span class="arrange__order">{{ index + 1 }}</span>
              <span class="reference-picker__title" :title="arrangingTitles.get(item.problem_id)">
                {{ arrangingTitles.get(item.problem_id) ?? item.problem_id.slice(0, 8) }}
              </span>
              <NButton
                size="tiny"
                quaternary
                type="error"
                @click="removeArrangeItem(item.problem_id)"
              >
                {{ t('action.delete') }}
              </NButton>
            </li>
          </ul>
        </div>
      </div>
      <template #footer>
        <div class="drawer-footer">
          <NButton @click="arrangingSet = null">{{ t('action.cancel') }}</NButton>
          <NButton type="primary" :loading="savingArrange" @click="saveArrange">
            {{ t('action.save') }}
          </NButton>
        </div>
      </template>
    </NModal>
  </WorkbenchShell>
</template>

<style scoped>
/* ============================================================
   通铺沉浸式布局：page-fill → n-card-content（零 padding）
   → team-fill（无外框、无卡片嵌套，线条分隔）
   ============================================================ */
.team-fill {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  /* 抵消应用壳卡片默认 padding：内容直接铺满，顶部无间距 */
  margin: calc(-1 * var(--n-padding-top, 20px)) calc(-1 * var(--n-padding-left, 24px))
    calc(-1 * var(--n-padding-bottom, 24px));
}

/* ======== Hero：中性底 + 主色几何 ========
   规则同 ContestDetailView 的 Hero：主色仅小面积点缀，不大面积铺色。
   底色比卡片深一档（surface-muted），主色只以「被裁切的圆」出现：
   右上实心巨弧 + 右下描边环，画面内不留完整圆形。 */
.hero {
  position: relative;
  flex-shrink: 0;
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
  overflow: hidden;
}
.hero--skeleton {
  padding: 24px;
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
.hero__avatar--skeleton {
  margin: -44px 0 0 28px;
}
/* 巨圆：圆心落在上沿外 252px，只露出底部一弧；
   填充用径向渐变（20% → 5% → 0），边缘化开，避免出现生硬的色块边界 */
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
/* 描边环：被右侧与底部各裁一截，与上方实心弧形成一虚一实 */
.hero__ring {
  position: absolute;
  width: 228px;
  height: 228px;
  border-radius: 999px;
  right: -104px;
  bottom: -120px;
  border: 1px solid color-mix(in srgb, var(--app-primary) 24%, transparent);
}
.hero__body {
  position: relative;
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 26px 32px 20px;
  flex-wrap: wrap;
  max-width: 1680px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}
.hero__avatar {
  width: 88px;
  height: 88px;
  border-radius: 10px;
  object-fit: cover;
  border: 3px solid var(--app-card-bg, #fff);
  box-shadow: 0 2px 12px rgb(0 0 0 / 8%);
  flex-shrink: 0;
  background: var(--app-muted-bg);
}
.hero__avatar--fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--app-text-secondary);
  font-size: 32px;
  font-weight: 800;
}
.hero__main {
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
/* 团队 ID：点击复制完整 ID，常态是弱化的文字而不是按钮 */
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
/* 动作区：预留扩展位，后续按钮直接追加；窄屏自动换行 */
.hero__actions {
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
/* 非 animated 模式 naive 不渲染 pane-wrapper，pane 直接挂在 .n-tabs 下 */
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
/* 空态：吃满 pane 剩余高度并垂直居中
   （.n-empty 自身已是 flex 列 + align-items: center，补 flex:1 + justify-content 居中） */
.pane-empty {
  flex: 1;
  min-height: 0;
  justify-content: center;
  padding: 56px 0;
}

/* 成员 / 申请：线条列表（分隔线行，无卡片边框） */
.member-grid {
  flex: 1;
  min-height: 0;
  grid-auto-rows: minmax(56px, auto);
  align-content: start;
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 0 48px;
}
.member-cell {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 8px;
  border-bottom: 1px solid var(--app-border);
  background: transparent;
  transition: background-color 0.15s ease;
}
.member-cell:hover {
  background: var(--app-muted-bg);
}
.member-cell__main {
  display: grid;
  gap: 2px;
  min-width: 0;
  flex: 1;
}
.member-cell__name {
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.member-cell__time {
  color: var(--app-text-secondary);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.member-cell__role {
  flex-shrink: 0;
}
.member-cell__actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
/* 行内「更多」操作：指针设备下 hover 才浮现，减少每行常驻图标的噪音；
   触屏（无 hover）与键盘 focus 时保持可见，不影响可操作性 */
@media (hover: hover) {
  .member-cell__ops {
    opacity: 0;
    transition: opacity 0.15s ease;
  }
  .member-cell:hover .member-cell__ops,
  .member-cell:focus-within .member-cell__ops {
    opacity: 1;
  }
}

/* 题库 / 题单列表表格：吃满滚动区，行内操作按钮 */
.pane-table {
  flex: 1;
  min-height: 0;
}
.cell-strong {
  font-weight: 600;
}
.cell-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

/* 分页钉底 */
.pane-pager {
  flex-shrink: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--app-border);
}
.pane-pager__total {
  font-size: 12px;
  color: var(--app-text-secondary);
  font-variant-numeric: tabular-nums;
}

/* 团队空间模块：工具行（搜索 / 管理动作） */
.pane-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding-bottom: 10px;
}
.pane-toolbar__spacer {
  flex: 1;
}
/* 可点击行（题库 / 比赛整行进上下文） */
.member-cell--link {
  cursor: pointer;
  transition: background-color 0.15s ease;
}
.member-cell--link:hover {
  background: var(--app-muted-bg);
}
.member-cell--link:hover .member-cell__name {
  color: var(--app-primary);
}
.member-cell--link:focus-visible {
  outline: 2px solid var(--app-primary);
  outline-offset: -2px;
}
.member-cell--stack {
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
}
.member-cell__row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.member-cell__row--ops {
  padding-left: 56px;
  gap: 8px;
}
.member-cell__avatar-text {
  width: 44px;
  height: 44px;
  border-radius: 999px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  background: var(--app-muted-bg);
  border: 1px solid var(--app-border);
  color: var(--app-text-secondary);
  font-size: 15px;
  font-weight: 650;
}
.member-cell__arrow {
  margin-left: auto;
  color: var(--app-text-secondary);
  flex-shrink: 0;
}

/* 引用 / 编排弹窗 */
.reference-picker {
  display: grid;
  gap: 12px;
}
.reference-picker__bar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.reference-picker__list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 320px;
  overflow: auto;
  display: grid;
  gap: 4px;
}
.reference-picker__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--app-border);
  border-radius: 6px;
}
.reference-picker__title {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.reference-picker__meta {
  color: var(--app-text-secondary);
  font-size: 12px;
  flex-shrink: 0;
}
.arrange {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
}
.arrange__source {
  max-height: 300px;
}
.arrange__list {
  max-height: 340px;
}
.arrange__label {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
}
.arrange__order {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  background: var(--app-muted-bg);
  color: var(--app-text-secondary);
  font-size: 12px;
}
@media (max-width: 760px) {
  .arrange {
    grid-template-columns: 1fr;
  }
}

/* ======== 邀请弹窗 ======== */
.invite-modal {
  display: grid;
  justify-items: center;
  gap: 12px;
}
.invite-modal__qr {
  border: 1px solid var(--app-border);
  border-radius: 8px;
  overflow: hidden;
  /* 组件 padding=0，留白由外层承担，同时避免圆角裁到码点 */
  padding: 10px;
}
.invite-modal__hint {
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 12px;
  text-align: center;
}
.invite-modal__link {
  width: 100%;
  display: grid;
  gap: 8px;
}
.invite-modal__url {
  font-size: 12px;
  color: var(--app-text-secondary);
  word-break: break-all;
  text-align: center;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.invite-modal__actions {
  display: flex;
  justify-content: center;
  gap: 8px;
}
.field-hint {
  color: var(--app-text-secondary);
  font-size: 12px;
  margin: 0;
}

/* ======== 编辑抽屉 ======== */
.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
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

/* 响应式 */
@media (max-width: 860px) {
  .hero__actions {
    margin-left: 0;
    width: 100%;
  }
  .hero__body {
    padding: 20px 16px;
  }
  .hero__avatar {
    width: 72px;
    height: 72px;
  }
  .module-tabs :deep(.n-tabs-nav),
  .module-tabs :deep(.n-tab-pane) {
    padding-left: 16px;
    padding-right: 16px;
  }
  .member-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
