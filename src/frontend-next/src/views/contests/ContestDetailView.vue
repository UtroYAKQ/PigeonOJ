<script setup lang="ts">
/**
 * 比赛详情（公开赛 / 团队比赛共用）：
 * 主页（公告 + 时间安排 + 说明）/ 题目 / 榜单 / 提交记录四个 tab。
 * 题目进入比赛上下文写题页；榜单封榜展示冻结快照，进行中 15s 轮询；
 * 提交记录比赛期间仅管理角色可见，赛后对所有登录用户开放。
 * 页面级 KeepAlive：切走暂停时钟与榜单轮询，返回时恢复并重拉详情。
 */
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { getContest, registerContest } from '@/api/contests'
import { getTeamContest, registerTeamContest } from '@/api/teams'
import ErrorState from '@/components/common/ErrorState.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import { Card } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { message } from '@/utils/feedback'
import ContestHeader from './components/ContestHeader.vue'
import OverviewPanel from './components/OverviewPanel.vue'
import ProblemsPanel from './components/ProblemsPanel.vue'
import RegisterDialog from './components/RegisterDialog.vue'
import StandingsPanel from './components/StandingsPanel.vue'
import SubmissionsPanel from './components/SubmissionsPanel.vue'
import type { ContestDetail } from '@/types'

type ContestTab = 'home' | 'problems' | 'board' | 'submissions'
const TAB_KEYS: ContestTab[] = ['home', 'problems', 'board', 'submissions']

function tabFromQuery(raw: unknown): ContestTab {
  const value = typeof raw === 'string' ? raw : ''
  return (TAB_KEYS as string[]).includes(value) ? (value as ContestTab) : 'home'
}

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const contestId = computed(() => String(route.params.cid ?? route.params.id))
const teamId = computed(() => (route.params.teamId ? String(route.params.teamId) : null))
/** 上下文基路径：团队比赛路由内导航不跳出团队前缀 */
const contextBase = computed(() =>
  teamId.value
    ? `/teams/${teamId.value}/contests/${contestId.value}`
    : `/contests/${contestId.value}`,
)

const detail = ref<ContestDetail | null>(null)
const loading = ref(true)
const registering = ref(false)
const registerOpen = ref(false)
const boardRefreshToken = ref(0)

const requestedTab = tabFromQuery(route.query.tab)
const activeTab = ref<ContestTab>(requestedTab)
const mountedTabs = ref<Set<ContestTab>>(new Set<ContestTab>(['home', requestedTab]))
watch(activeTab, (tab) => {
  mountedTabs.value.add(tab)
})

/** 模块 tab 可见性：管理角色随时可见；赛前对非管理角色隐藏；
 *  比赛期间仅已报名者可见；赛后对所有用户开放 */
const moduleTabsVisible = computed(() => {
  const current = detail.value
  if (!current) return false
  if (current.can_manage) return true
  if (current.status === 'scheduled') return false
  if (current.status === 'running') return current.my_registration === 'registered'
  return true
})

/** 被赛前隐藏的模块 tab 一律回落主页 */
function clampTab(tab: ContestTab): ContestTab {
  return tab === 'home' || moduleTabsVisible.value ? tab : 'home'
}

function tabClass(tab: ContestTab, layout: string): string {
  return activeTab.value === tab ? layout : 'hidden'
}

watch(moduleTabsVisible, (visible) => {
  if (!visible && activeTab.value !== 'home') activeTab.value = 'home'
})

watch(
  () => route.query.tab,
  (raw) => {
    const next = tabFromQuery(raw)
    // 详情未就绪时先按查询参数进入，加载完成后再按可见性校正（修复旧页面深链被吞）
    activeTab.value = detail.value ? clampTab(next) : next
  },
)

async function load(silent = false): Promise<void> {
  if (!silent) loading.value = true
  try {
    detail.value = await (teamId.value
      ? getTeamContest(teamId.value, contestId.value)
      : getContest(contestId.value))
    const next = clampTab(activeTab.value)
    if (next !== activeTab.value) activeTab.value = next
  } catch (error) {
    if (!silent) message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (!silent) loading.value = false
  }
}

function onTabChange(value: string | number): void {
  activeTab.value = value as ContestTab
}

function openProblem(problemId: string): void {
  void router.push(`${contextBase.value}/problems/${problemId}`)
}

function goEdit(): void {
  if (detail.value?.status !== 'scheduled') return
  void router.push(
    teamId.value
      ? `/teams/${teamId.value}/contests/${contestId.value}/edit/basic`
      : `/admin/contests/${contestId.value}/edit/basic`,
  )
}

function goTools(): void {
  void router.push(
    teamId.value
      ? `/teams/${teamId.value}/contests/${contestId.value}/tools`
      : `/admin/contests/${contestId.value}/tools`,
  )
}

async function register(): Promise<void> {
  if (!detail.value || registering.value) return
  registering.value = true
  try {
    await (teamId.value
      ? registerTeamContest(teamId.value, detail.value.id)
      : registerContest(detail.value.id))
    message.success(t('common.success'))
    registerOpen.value = false
    await load(true)
    boardRefreshToken.value += 1
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    registering.value = false
  }
}

// ---- 倒计时时钟：KeepAlive 切走时停表，返回时恢复 ----
const nowTick = ref(Date.now())
let clockTimer: number | null = null
const pageActive = ref(true)

function startClock(): void {
  if (clockTimer !== null) return
  clockTimer = window.setInterval(() => {
    nowTick.value = Date.now()
  }, 1000)
}

function stopClock(): void {
  if (clockTimer !== null) {
    window.clearInterval(clockTimer)
    clockTimer = null
  }
}

onMounted(() => {
  void load()
  startClock()
})

onActivated(() => {
  pageActive.value = true
  startClock()
  if (detail.value) void load()
})

onDeactivated(() => {
  pageActive.value = false
  stopClock()
})

onBeforeUnmount(stopClock)
</script>

<template>
  <WorkbenchShell>
    <div class="flex min-h-0 flex-1 flex-col gap-3">
      <Card
        v-if="!detail"
        class="grid flex-1 place-items-center"
      >
        <div v-if="loading" class="w-full max-w-xl space-y-4 p-8">
          <div class="flex items-center gap-4">
            <div class="size-16 animate-pulse rounded-lg bg-muted" />
            <div class="flex-1 space-y-2">
              <div class="h-4 w-1/3 animate-pulse rounded bg-muted" />
              <div class="h-3 w-2/3 animate-pulse rounded bg-muted" />
              <div class="h-3 w-1/2 animate-pulse rounded bg-muted" />
            </div>
          </div>
        </div>
        <div v-else class="flex flex-col items-center gap-3 py-16">
          <ErrorState :message="t('common.loadFailed')" @retry="load" />
        </div>
      </Card>

      <template v-else>
        <ContestHeader
          :detail="detail"
          :now="nowTick"
          :registering="registering"
          @register="registerOpen = true"
          @edit="goEdit"
          @tools="goTools"
        />

        <Tabs
          :model-value="activeTab"
          :unmount-on-hide="false"
          class="min-h-0 flex-1 gap-2"
          @update:model-value="onTabChange"
        >
          <TabsList class="max-w-full shrink-0 overflow-x-auto overflow-y-hidden">
            <TabsTrigger value="home" class="px-3 text-[12.5px]">
              {{ t('contests.detail.tabHome') }}
            </TabsTrigger>
            <TabsTrigger v-if="moduleTabsVisible" value="problems" class="px-3 text-[12.5px]">
              {{ t('contests.detail.tabProblems') }}
            </TabsTrigger>
            <TabsTrigger v-if="moduleTabsVisible" value="board" class="px-3 text-[12.5px]">
              {{ t('contests.detail.tabBoard') }}
            </TabsTrigger>
            <TabsTrigger
              v-if="moduleTabsVisible"
              value="submissions"
              class="px-3 text-[12.5px]"
            >
              {{ t('contests.detail.tabSubmissions') }}
            </TabsTrigger>
          </TabsList>

          <TabsContent
            v-if="mountedTabs.has('home')"
            value="home"
            :class="tabClass('home', 'min-h-0 overflow-y-auto pr-1')"
          >
            <OverviewPanel :detail="detail" />
          </TabsContent>

          <TabsContent
            v-if="moduleTabsVisible && mountedTabs.has('problems')"
            value="problems"
            :class="tabClass('problems', 'flex min-h-0 flex-col')"
          >
            <ProblemsPanel :detail="detail" @open="openProblem" />
          </TabsContent>

          <TabsContent
            v-if="moduleTabsVisible && mountedTabs.has('board')"
            value="board"
            :class="tabClass('board', 'flex min-h-0 flex-col')"
          >
            <StandingsPanel
              :detail="detail"
              :team-id="teamId"
              :context-base="contextBase"
              :active="activeTab === 'board'"
              :page-active="pageActive"
              :refresh-token="boardRefreshToken"
            />
          </TabsContent>

          <TabsContent
            v-if="moduleTabsVisible && mountedTabs.has('submissions')"
            value="submissions"
            :class="tabClass('submissions', 'flex min-h-0 flex-col')"
          >
            <SubmissionsPanel
              :detail="detail"
              :team-id="teamId"
              :context-base="contextBase"
              :active="activeTab === 'submissions'"
            />
          </TabsContent>
        </Tabs>
      </template>
    </div>

    <RegisterDialog
      v-if="detail"
      v-model:open="registerOpen"
      :detail="detail"
      :registering="registering"
      @confirm="register"
    />
  </WorkbenchShell>
</template>
