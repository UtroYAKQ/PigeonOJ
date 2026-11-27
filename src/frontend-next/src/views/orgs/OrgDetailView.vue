<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch, type Component } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { BookOpen, Copy, Loader2, Settings2, UserRound, Users } from '@lucide/vue'

import { adminGetOrg } from '@/api/admin'
import { getOrg } from '@/api/orgs'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import ErrorState from '@/components/common/ErrorState.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useUserStore } from '@/stores/user'
import { copyToClipboard } from '@/utils/clipboard'
import { message } from '@/utils/feedback'
import type { OrgDetail } from '@/types'
import OrgMembersPanel from './components/OrgMembersPanel.vue'
import OrgProblemsPanel from './components/OrgProblemsPanel.vue'
import OrgSettingsPanel from './components/OrgSettingsPanel.vue'
import OrgTeamsPanel from './components/OrgTeamsPanel.vue'

const route = useRoute()
const { t } = useI18n()
const userStore = useUserStore()

const adminMode = computed(() => route.path.startsWith('/admin'))
const orgId = String(route.params.orgId ?? route.params.id)
const org = ref<OrgDetail | null>(null)
const loading = ref(false)
const failed = ref(false)

const siteAdmin = computed(() => userStore.isAdmin)
const canManage = computed(() => siteAdmin.value || org.value?.my_role === 'admin')
const canWrite = computed(() => !adminMode.value && canManage.value)
/** 组织题库：全体成员可读写（站点 admin 同权）；admin 管理视图只读 */
const canManageProblems = computed(
  () => !adminMode.value && (siteAdmin.value || org.value?.my_role != null),
)
const forbidden = ref(false)

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  forbidden.value = false
  try {
    org.value = adminMode.value ? await adminGetOrg(orgId) : await getOrg(orgId)
  } catch (error) {
    org.value = null
    const code = (error as { code?: number }).code
    forbidden.value = code === 2003
    failed.value = !forbidden.value
    if (!forbidden.value) {
      message.error(error instanceof Error ? error.message : t('orgs.detail.loadFailed'))
    }
  } finally {
    loading.value = false
  }
}

type OrgTab = 'members' | 'teams' | 'problems' | 'settings'
const activeTab = ref<OrgTab>('members')
const visited = reactive<Record<OrgTab, boolean>>({
  members: true,
  teams: false,
  problems: false,
  settings: false,
})

function onTabChange(tab: OrgTab): void {
  activeTab.value = tab
  visited[tab] = true
}

const tabs = computed<Array<{ key: OrgTab; label: string; icon: Component }>>(() => {
  const items: Array<{ key: OrgTab; label: string; icon: Component }> = [
    { key: 'members', label: t('orgs.detail.tabMembers'), icon: UserRound },
    { key: 'teams', label: t('orgs.detail.tabTeams'), icon: Users },
    { key: 'problems', label: t('orgs.detail.tabProblems'), icon: BookOpen },
  ]
  if (canManage.value) {
    items.push({ key: 'settings', label: t('orgs.detail.tabSettings'), icon: Settings2 })
  }
  return items
})

const activeTabInfo = computed(
  () => tabs.value.find((tab) => tab.key === activeTab.value) ?? tabs.value[0],
)

// 管理权限被撤销后设置面板不再可见，回落到成员面板避免空白
watch(canManage, (value) => {
  if (!value && activeTab.value === 'settings') activeTab.value = 'members'
})

const statusTone = computed(() => (org.value?.status === 'active' ? 'success' : 'default'))
const statusLabel = computed(() =>
  org.value?.status === 'active' ? t('orgs.detail.statusActive') : t('orgs.detail.statusDisbanded'),
)

async function copyId(): Promise<void> {
  if (!org.value) return
  if (await copyToClipboard(org.value.id)) message.success(t('problems.detail.copied'))
}

onMounted(load)
</script>

<template>
  <WorkbenchShell>
    <div v-if="loading && !org" class="grid min-h-0 flex-1 place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <Card
      v-else-if="forbidden"
      class="grid min-h-0 flex-1 place-items-center"
    >
      <ErrorState :message="t('orgs.detail.forbidden')">
        <template #actions>
          <Button variant="outline" size="sm" @click="load">{{ t('action.refresh') }}</Button>
        </template>
      </ErrorState>
    </Card>

    <Card
      v-else-if="failed || !org"
      class="grid min-h-0 flex-1 place-items-center"
    >
      <ErrorState :message="t('orgs.detail.loadFailed')" @retry="load" />
    </Card>

    <template v-else>
      <!-- 上半区：组织摘要卡 -->
      <Card
        class="flex shrink-0 items-start gap-4 px-4 py-4 md:px-5"
      >
        <BaseAvatar
          :src="org.avatar_url"
          :name="org.name"
          kind="team"
          :size="56"
          :round="false"
          :radius="10"
          bordered
        />
        <div class="min-w-0 flex-1 space-y-2">
          <div class="flex flex-wrap items-center gap-2">
            <h1 class="min-w-0 truncate text-[20px] font-semibold leading-tight tracking-tight">
              {{ org.name }}
            </h1>
            <ToneBadge :tone="statusTone" :label="statusLabel" />
            <ToneBadge
              v-if="!siteAdmin && org.my_role"
              :tone="org.my_role === 'admin' ? 'warning' : 'default'"
              dot
              :label="org.my_role === 'admin' ? t('orgs.role.admin') : t('orgs.role.member')"
            />
            <ToneBadge v-if="siteAdmin" tone="primary" :label="t('orgs.role.siteAdmin')" />
          </div>
          <p
            class="max-w-[80ch] text-[13px] leading-5 text-muted-foreground"
            :class="{ 'opacity-60': !org.description }"
          >
            {{ org.description || t('orgs.detail.descEmpty') }}
          </p>
          <div
            class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-muted-foreground"
          >
            <span>{{ t('orgs.list.memberCount') }} {{ org.member_count }}</span>
            <span aria-hidden="true">·</span>
            <span>{{ t('orgs.list.teamCount') }} {{ org.team_count }}</span>
            <span aria-hidden="true">·</span>
            <button
              type="button"
              class="inline-flex items-center gap-1 tabular-nums transition-colors hover:text-foreground"
              @click="copyId"
            >
              {{ t('orgs.detail.orgId') }} {{ org.id.slice(0, 8) }}
              <Copy class="size-3" />
            </button>
          </div>
        </div>

        <div v-if="canWrite" class="flex shrink-0 flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" @click="onTabChange('settings')">
            <Settings2 class="size-4" />
            {{ t('orgs.detail.editInfo') }}
          </Button>
        </div>
        <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
      </Card>

      <!-- 下半区：左侧功能按钮 + 右侧内容，窄屏按钮横排置顶 -->
      <Card
        class="mt-4 flex min-h-0 flex-1 flex-col overflow-hidden lg:flex-row"
      >
        <nav
          class="flex shrink-0 gap-1 overflow-x-auto border-b border-border p-2 lg:w-[220px] lg:flex-col lg:overflow-x-hidden lg:border-b-0 lg:border-r lg:p-3"
          :aria-label="t('orgs.detail.workspace')"
        >
          <p
            class="hidden px-2 pb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground lg:block"
          >
            {{ t('orgs.detail.workspace') }}
          </p>
          <Button
            v-for="tab in tabs"
            :key="tab.key"
            variant="ghost"
            size="sm"
            class="h-9 shrink-0 justify-start gap-2.5 px-2.5 text-[13px] font-medium lg:w-full"
            :class="
              activeTab === tab.key
                ? 'bg-accent text-foreground'
                : 'text-muted-foreground hover:text-foreground'
            "
            :aria-current="activeTab === tab.key ? 'page' : undefined"
            @click="onTabChange(tab.key)"
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
            <OrgMembersPanel
              v-if="visited.members"
              v-show="activeTab === 'members'"
              :org-id="org.id"
              :can-manage="canManage"
              :admin-mode="adminMode"
            />
            <OrgTeamsPanel
              v-if="visited.teams"
              v-show="activeTab === 'teams'"
              :org-id="org.id"
              :can-manage="canWrite"
              :admin-mode="adminMode"
            />
            <OrgProblemsPanel
              v-if="visited.problems"
              v-show="activeTab === 'problems'"
              :org-id="org.id"
              :can-manage="canManageProblems"
            />
            <OrgSettingsPanel
              v-if="visited.settings && canManage"
              v-show="activeTab === 'settings'"
              :org="org"
              :can-manage="canManage"
              :site-admin="siteAdmin"
              @refresh="load"
            />
          </div>
        </div>
      </Card>
    </template>
  </WorkbenchShell>
</template>
