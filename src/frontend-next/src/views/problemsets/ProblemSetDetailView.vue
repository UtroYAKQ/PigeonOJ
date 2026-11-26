<script setup lang="ts">
/**
 * 题单详情 / 刷题页（前台浏览）：标题区 + tabs（信息 / 题目列表）。
 * 同一组件被团队上下文复用：按 route.params.teamId 分派团队端点，
 * 题内跳转与面包屑均留在本上下文（frontend.md 路由上下文隔离）。
 */
import { computed, onActivated, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { getProblemSet } from '@/api/problemSets'
import { getTeamProblemSet } from '@/api/teams'
import ErrorState from '@/components/common/ErrorState.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import { Card } from '@/components/ui/card'
import ProblemSetOverview from '@/components/problemsets/ProblemSetOverview.vue'
import ProblemSetProblemsTable from '@/components/problemsets/ProblemSetProblemsTable.vue'
import ProblemSetVisibilityBadge from '@/components/problemsets/ProblemSetVisibilityBadge.vue'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { ProblemSetDetail, ProblemSetItem } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const detail = ref<ProblemSetDetail | null>(null)
const activeTab = ref<'info' | 'problems'>('info')

/** 上下文取参：团队上下文读团队端点，否则题单统一入口 */
const teamId = computed(() => (route.params.teamId ? String(route.params.teamId) : null))
const setId = computed(() => String(route.params.setId ?? route.params.id ?? ''))

async function load(): Promise<void> {
  loading.value = true
  try {
    detail.value = await (teamId.value
      ? getTeamProblemSet(teamId.value, setId.value)
      : getProblemSet(setId.value))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(load)
// keepAlive 页面：从编排页返回时命中缓存实例（onMounted 不再执行），
// onActivated 强制重拉，保证题单内容与服务器一致
onActivated(() => {
  if (detail.value) void load()
})

/** 完成进度：当前用户 AC 题数 / 题单题数（匿名=0） */
const solvedCount = computed(
  () => (detail.value?.items ?? []).filter((item) => item.solved === true).length,
)
const totalCount = computed(() => detail.value?.items.length ?? 0)
const progressPercent = computed(() =>
  totalCount.value ? Math.round((solvedCount.value / totalCount.value) * 100) : 0,
)

function onTabChange(value: unknown): void {
  activeTab.value = String(value) === 'problems' ? 'problems' : 'info'
}

/** 题内跳转不跳出上下文：团队上下文走 /teams/:teamId/sets/:setId/problems/:pid */
function openProblem(item: ProblemSetItem): void {
  if (!detail.value) return
  router.push(
    teamId.value
      ? `/teams/${teamId.value}/sets/${detail.value.id}/problems/${item.problem_id}`
      : `/problem-sets/${detail.value.id}/problems/${item.problem_id}`,
  )
}
</script>

<template>
  <WorkbenchShell>
    <template #title>
      <div class="flex flex-wrap items-center gap-2">
        <h1 class="truncate text-xl font-semibold leading-tight tracking-tight">
          {{ detail?.title ?? t('problemSets.detail.title') }}
        </h1>
        <ProblemSetVisibilityBadge v-if="detail" :visibility="detail.visibility" />
        <ToneBadge
          v-if="detail?.status === 'archived'"
          tone="warning"
          :label="t('problemSets.detail.archived')"
        />
      </div>
      <p v-if="detail" class="mt-1 text-[12.5px] text-muted-foreground">
        {{ t('problemSets.detail.ownerLabel', { name: detail.owner_name || '--' }) }}
        <span class="mx-1.5">·</span>
        {{ formatDateTime(detail.created_at) }}
      </p>
    </template>

    <template #actions>
      <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
    </template>

    <div v-if="loading && !detail" class="grid min-h-0 flex-1 place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <Card
      v-else-if="!detail"
      class="grid min-h-0 flex-1 place-items-center"
    >
      <ErrorState :message="t('common.loadFailed')" @retry="load" />
    </Card>

    <Tabs
      v-else-if="detail"
      :model-value="activeTab"
      class="min-h-0 flex-1 gap-3"
      @update:model-value="onTabChange"
    >
      <TabsList class="shrink-0">
        <TabsTrigger value="info" class="px-3 text-[12px]">
          {{ t('problemSets.detail.tabInfo') }}
        </TabsTrigger>
        <TabsTrigger value="problems" class="px-3 text-[12px]">
          {{ t('problemSets.detail.problems') }} · {{ totalCount }}
        </TabsTrigger>
      </TabsList>

      <TabsContent value="info" class="min-h-0 overflow-y-auto">
        <ProblemSetOverview
          :detail="detail"
          :solved="solvedCount"
          :total="totalCount"
          :percent="progressPercent"
        />
      </TabsContent>

      <TabsContent value="problems" class="flex min-h-0 flex-col pb-1">
        <ProblemSetProblemsTable
          :items="detail.items"
          :empty-text="t('problemSets.detail.empty')"
          @open="openProblem"
        />
      </TabsContent>
    </Tabs>
  </WorkbenchShell>
</template>
