<script setup lang="ts">
/**
 * 团队详情（/teams/:id）：成员 / 团队题库 / 团队题单 / 团队比赛 / 邀请 / 设置。
 * 数据加载按面板拆分到子组件（各自维护筛选、分页与竞态守卫）；
 * 本页只负责团队详情、角色门控、tab 编排与退出 / 解散后的成员关系脏标记。
 */
import { computed, onMounted, ref, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  BookOpen,
  Layers,
  Loader2,
  Settings2,
  ShieldAlert,
  Trophy,
  UserPlus,
  Users,
} from '@lucide/vue'

import { getTeam, submitTeamApplication } from '@/api/teams'
import { ApiError } from '@/api/http'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useTeamsStore } from '@/stores/teams'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'
import type { TeamDetail } from '@/types'
import ContestsPanel from './components/ContestsPanel.vue'
import InvitesPanel from './components/InvitesPanel.vue'
import MembersPanel from './components/MembersPanel.vue'
import ProblemsPanel from './components/ProblemsPanel.vue'
import SetsPanel from './components/SetsPanel.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import TeamHeader from './components/TeamHeader.vue'

type TeamTab = 'members' | 'problems' | 'sets' | 'contests' | 'invites' | 'settings'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const teamId = computed(() => String(route.params.id ?? route.params.teamId))
const team = ref<TeamDetail | null>(null)
const loading = ref(true)
/** 403（非团队成员）：给出「申请加入」出口而非裸错误 */
const forbidden = ref(false)
const applying = ref(false)
const applied = ref(false)

const isCreator = computed(() => team.value?.my_role === 'creator')
const isAdmin = computed(() => isCreator.value || team.value?.my_role === 'admin')
const currentUserId = computed(() => userStore.user?.id ?? '')

const activeTab = ref<TeamTab>('members')
const mountedTabs = ref<Set<TeamTab>>(new Set<TeamTab>(['members']))
watch(activeTab, (tab) => {
  mountedTabs.value.add(tab)
})

/** 成员增删后通知成员面板重拉（审批通过 / 踢出等跨面板动作） */
const membersSignal = ref(0)

async function loadTeam(): Promise<void> {
  loading.value = true
  try {
    team.value = await getTeam(teamId.value)
    forbidden.value = false
  } catch (error) {
    // 2003 = 非团队成员（详情仅成员可见）
    forbidden.value = error instanceof ApiError && error.code === 2003
    if (!team.value) {
      message.error(error instanceof Error ? error.message : t('teams.detail.loadFailed'))
    }
  } finally {
    loading.value = false
  }
}

async function refreshTeam(): Promise<void> {
  try {
    team.value = await getTeam(teamId.value)
  } catch {
    /* 静默：成员数等次要信息刷新失败不打断当前操作 */
  }
}

async function applyFromForbidden(): Promise<void> {
  if (applying.value) return
  applying.value = true
  try {
    await submitTeamApplication(teamId.value)
    applied.value = true
    message.success(t('teams.list.applySuccess'))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    applying.value = false
  }
}

function onRosterChanged(): void {
  membersSignal.value += 1
  void refreshTeam()
}

function onLeft(): void {
  // 成员关系已变更：列表页经脏标记重拉
  useTeamsStore().markMembershipChanged()
  void router.push('/teams/mine')
}

function onSettingsUpdated(updated: TeamDetail): void {
  team.value = updated
}

/** tab 可见性：邀请 / 设置为管理任务；设置对所有成员开放（含退出入口） */
const tabs = computed<Array<{ key: TeamTab; label: string; icon: Component }>>(() => {
  const items: Array<{ key: TeamTab; label: string; icon: Component }> = [
    { key: 'members', label: t('teams.detail.tabMembers'), icon: Users },
    { key: 'problems', label: t('teams.modules.problems'), icon: BookOpen },
    { key: 'sets', label: t('teams.modules.sets'), icon: Layers },
    { key: 'contests', label: t('teams.modules.contests'), icon: Trophy },
  ]
  if (isAdmin.value) {
    items.push({ key: 'invites', label: t('teams.settings.inviteTitle'), icon: UserPlus })
  }
  items.push({ key: 'settings', label: t('teams.detail.tabSettings'), icon: Settings2 })
  return items
})

const activeTabInfo = computed(
  () => tabs.value.find((tab) => tab.key === activeTab.value) ?? tabs.value[0],
)

// 角色被降级后邀请 tab 不再可见：回落到成员 tab，避免空白面板
watch(isAdmin, (value) => {
  if (!value && activeTab.value === 'invites') activeTab.value = 'members'
})

onMounted(loadTeam)
</script>

<template>
  <WorkbenchShell>
    <div class="flex min-h-0 flex-1 flex-col gap-3">
      <!-- 加载骨架 -->
      <Card
        v-if="!team && loading"
        class="grid flex-1 place-items-center"
      >
        <div class="w-full max-w-xl space-y-4 p-8">
          <div class="flex items-center gap-4">
            <div class="size-16 animate-pulse rounded-xl bg-muted" />
            <div class="flex-1 space-y-2">
              <div class="h-4 w-1/3 animate-pulse rounded bg-muted" />
              <div class="h-3 w-2/3 animate-pulse rounded bg-muted" />
              <div class="h-3 w-1/2 animate-pulse rounded bg-muted" />
            </div>
          </div>
        </div>
      </Card>

      <!-- 失败 / 非成员 -->
      <Card
        v-else-if="!team"
        class="grid flex-1 place-items-center"
      >
        <div class="flex max-w-[520px] flex-col items-center gap-3 px-6 py-16 text-center">
          <ShieldAlert class="size-7 text-muted-foreground" :stroke-width="1.6" />
          <p class="text-[13px] leading-6 text-muted-foreground">
            {{ forbidden ? t('teams.detail.forbidden') : t('teams.detail.loadFailed') }}
          </p>
          <div class="flex flex-wrap items-center justify-center gap-2">
            <Button
              v-if="forbidden"
              size="sm"
              :disabled="applying || applied"
              @click="applyFromForbidden"
            >
              <Loader2 v-if="applying" class="size-4 animate-spin" />
              {{ t('teams.list.applyJoin') }}
            </Button>
            <Button variant="outline" size="sm" @click="loadTeam">
              {{ t('action.refresh') }}
            </Button>
          </div>
        </div>
      </Card>

      <template v-else>
        <TeamHeader
          :team="team"
          :is-admin="isAdmin"
          :is-creator="isCreator"
          @invite="activeTab = 'invites'"
          @edit="activeTab = 'settings'"
        />

        <!-- 下半区：左侧功能按钮 + 右侧内容，窄屏按钮横排置顶 -->
        <Card
          class="mt-4 flex min-h-[420px] flex-1 flex-col overflow-hidden lg:flex-row"
        >
          <nav
            class="scrollbar-none flex shrink-0 gap-1 overflow-x-auto border-b border-border p-2 lg:w-[220px] lg:flex-col lg:overflow-x-hidden lg:border-b-0 lg:border-r lg:p-3"
            :aria-label="t('teams.detail.workspace')"
          >
            <p
              class="hidden px-2 pb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground lg:block"
            >
              {{ t('teams.detail.workspace') }}
            </p>
            <Button
              v-for="tab in tabs"
              :key="tab.key"
              variant="ghost"
              size="sm"
              class="h-10 shrink-0 justify-start gap-2.5 px-2.5 text-[13px] font-medium lg:h-9 lg:w-full"
              :class="
                activeTab === tab.key
                  ? 'bg-accent text-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              "
              :aria-current="activeTab === tab.key ? 'page' : undefined"
              @click="activeTab = tab.key"
            >
              <component :is="tab.icon" class="size-4 shrink-0" :stroke-width="1.8" />
              {{ tab.label }}
            </Button>
          </nav>

          <div class="flex min-h-0 min-w-0 flex-1 flex-col">
            <header class="flex shrink-0 items-center gap-2 border-b border-border px-4 py-3">
              <component
                :is="activeTabInfo.icon"
                class="size-4 text-muted-foreground"
                :stroke-width="1.8"
              />
              <h2 class="text-[14px] font-semibold">{{ activeTabInfo.label }}</h2>
            </header>

            <div class="flex min-h-0 flex-1 flex-col gap-3 p-3 lg:p-4">
              <MembersPanel
                v-if="mountedTabs.has('members')"
                v-show="activeTab === 'members'"
                :team-id="teamId"
                :is-creator="isCreator"
                :is-admin="isAdmin"
                :current-user-id="currentUserId"
                :refresh-signal="membersSignal"
                @changed="refreshTeam"
              />
              <ProblemsPanel
                v-if="mountedTabs.has('problems')"
                v-show="activeTab === 'problems'"
                :team-id="teamId"
                :is-admin="isAdmin"
              />
              <SetsPanel
                v-if="mountedTabs.has('sets')"
                v-show="activeTab === 'sets'"
                :team-id="teamId"
                :is-admin="isAdmin"
              />
              <ContestsPanel
                v-if="mountedTabs.has('contests')"
                v-show="activeTab === 'contests'"
                :team-id="teamId"
                :is-admin="isAdmin"
              />
              <InvitesPanel
                v-if="isAdmin && mountedTabs.has('invites')"
                v-show="activeTab === 'invites'"
                :team-id="teamId"
                @members-changed="onRosterChanged"
              />
              <SettingsPanel
                v-if="mountedTabs.has('settings')"
                v-show="activeTab === 'settings'"
                :team="team"
                :is-admin="isAdmin"
                :is-creator="isCreator"
                @updated="onSettingsUpdated"
                @left="onLeft"
              />
            </div>
          </div>
        </Card>
      </template>
    </div>
  </WorkbenchShell>
</template>
