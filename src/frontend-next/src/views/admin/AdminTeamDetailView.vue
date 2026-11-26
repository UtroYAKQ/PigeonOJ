<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { adminGetTeam } from '@/api/admin'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { message } from '@/utils/feedback'
import TeamSummaryCard from './team-components/TeamSummaryCard.vue'
import TeamContestsTable from './team-components/TeamContestsTable.vue'
import TeamMembersTable from './team-components/TeamMembersTable.vue'
import TeamProblemsTable from './team-components/TeamProblemsTable.vue'
import TeamSetsTable from './team-components/TeamSetsTable.vue'
import type { TeamAdminDetail } from '@/types'

type TeamModule = 'members' | 'problems' | 'sets' | 'contests'

const MODULES: Array<{ value: TeamModule; labelKey: string }> = [
  { value: 'members', labelKey: 'admin.teams.tabMembers' },
  { value: 'problems', labelKey: 'admin.teams.tabProblems' },
  { value: 'sets', labelKey: 'admin.teams.tabSets' },
  { value: 'contests', labelKey: 'admin.teams.tabContests' },
]

const route = useRoute()
const { t } = useI18n()
const teamId = String(route.params.id)

const detail = ref<TeamAdminDetail | null>(null)
const loadFailed = ref(false)

async function load(): Promise<void> {
  loadFailed.value = false
  try {
    detail.value = await adminGetTeam(teamId)
  } catch (error) {
    detail.value = null
    loadFailed.value = true
    message.error(error instanceof Error ? error.message : t('admin.teams.loadFailed'))
  }
}

onMounted(load)

// 模块 tab 懒加载：首次切到才挂载，之后常驻（切换不重置分页 / 筛选）
const activeModule = ref<TeamModule>('members')
const visited = reactive<Record<TeamModule, boolean>>({
  members: true,
  problems: false,
  sets: false,
  contests: false,
})

function onModuleChange(value: string | number): void {
  const module = String(value) as TeamModule
  activeModule.value = module
  visited[module] = true
}
</script>

<template>
  <WorkbenchShell>
    <div v-if="!detail" class="grid min-h-[320px] flex-1 place-items-center">
      <div v-if="loadFailed" class="flex flex-col items-center gap-3 text-center">
        <p class="text-[13px] text-muted-foreground">{{ t('admin.teams.loadFailed') }}</p>
        <Button variant="outline" size="sm" @click="load">{{ t('action.refresh') }}</Button>
      </div>
      <Loader2 v-else class="size-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="detail">
      <TeamSummaryCard :detail="detail" />

      <Tabs
        :model-value="activeModule"
        class="mt-3 flex min-h-0 flex-1 flex-col gap-0"
        @update:model-value="onModuleChange"
      >
        <TabsList class="shrink-0">
          <TabsTrigger
            v-for="module in MODULES"
            :key="module.value"
            :value="module.value"
            class="px-3 text-[12px]"
          >
            {{ t(module.labelKey) }}
          </TabsTrigger>
        </TabsList>

        <TabsContent
          v-if="visited.members"
          value="members"
          force-mount
          class="mt-2.5 flex min-h-0 flex-1 flex-col"
        >
          <TeamMembersTable :team-id="teamId" />
        </TabsContent>
        <TabsContent
          v-if="visited.problems"
          value="problems"
          force-mount
          class="mt-2.5 flex min-h-0 flex-1 flex-col"
        >
          <TeamProblemsTable :team-id="teamId" />
        </TabsContent>
        <TabsContent
          v-if="visited.sets"
          value="sets"
          force-mount
          class="mt-2.5 flex min-h-0 flex-1 flex-col"
        >
          <TeamSetsTable :team-id="teamId" />
        </TabsContent>
        <TabsContent
          v-if="visited.contests"
          value="contests"
          force-mount
          class="mt-2.5 flex min-h-0 flex-1 flex-col"
        >
          <TeamContestsTable :team-id="teamId" />
        </TabsContent>
      </Tabs>
    </template>
  </WorkbenchShell>
</template>
