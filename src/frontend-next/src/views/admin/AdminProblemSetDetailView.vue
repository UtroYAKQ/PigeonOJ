<script setup lang="ts">
/**
 * 题单编排页（管理后台 / 团队空间同款）：点进来即编排。
 * 左栏 Markdown 说明，右栏题目列表（拖拽 / 上移 / 下移 / 移除即时保存，「添加题目」打开选择器）。
 * 团队上下文（route.params.teamId）走团队题单端点 + arrangeable 候选源。
 */
import { computed, onActivated, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2, Plus } from '@lucide/vue'

import { archiveProblemSet, getProblemSet, replaceProblemSetItems } from '@/api/problemSets'
import {
  archiveTeamProblemSet,
  getTeamProblemSet,
  replaceTeamProblemSetItems,
  searchTeamArrangeableProblems,
} from '@/api/teams'
import EmptyState from '@/components/common/EmptyState.vue'
import MarkdownView from '@/components/common/MarkdownView.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import ProblemPicker from '@/components/problemsets/ProblemPicker.vue'
import ProblemSetArrangeTable from '@/components/problemsets/ProblemSetArrangeTable.vue'
import ProblemSetVisibilityBadge from '@/components/problemsets/ProblemSetVisibilityBadge.vue'
import { Button } from '@/components/ui/button'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import type { PageResult, ProblemSetDetail, ProblemSetItem, ProblemSummary } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const teamId = computed(() => (route.params.teamId ? String(route.params.teamId) : null))
const setId = computed(() => String(route.params.setId ?? route.params.id))
const loading = ref(false)
const detail = ref<ProblemSetDetail | null>(null)
/** 编排操作瞬时保存中（行内 ops 与添加按钮共用，避免并发写） */
const arranging = ref(false)
const pickerShow = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    detail.value = await (teamId.value
      ? getTeamProblemSet(teamId.value, setId.value)
      : getProblemSet(setId.value))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
    router.push(teamId.value ? `/teams/${teamId.value}` : '/admin/problem-sets')
  } finally {
    loading.value = false
  }
}

onMounted(load)
// 管理端题单详情为 keepAlive 页面：从编辑信息页返回时重拉，避免标题 / 介绍过期
onActivated(() => {
  if (detail.value) void load()
})

/** 行内编排落库：以当前列表全量替换（含 sort_order），成功后刷新基线 */
async function persistItems(items: ProblemSetItem[]): Promise<void> {
  arranging.value = true
  try {
    const body = {
      items: items.map((item, index) => ({ problem_id: item.problem_id, sort_order: index })),
    }
    await (teamId.value
      ? replaceTeamProblemSetItems(teamId.value, setId.value, body)
      : replaceProblemSetItems(setId.value, body))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
    await load() // 失败回滚到服务器权威状态
  } finally {
    arranging.value = false
  }
}

function onPicked(problem: ProblemSummary): void {
  if (!detail.value || arranging.value) return
  if (detail.value.items.some((item) => item.problem_id === problem.id)) return
  const items: ProblemSetItem[] = [
    ...detail.value.items,
    {
      problem_id: problem.id,
      title: problem.title,
      difficulty: problem.difficulty ?? null,
      time_limit_ms: problem.time_limit_ms,
      memory_limit_mb: problem.memory_limit_mb,
      sort_order: detail.value.items.length,
    },
  ]
  detail.value = { ...detail.value, items }
  void persistItems(items)
}

function removeItem(row: ProblemSetItem): void {
  if (!detail.value || arranging.value) return
  const items = detail.value.items.filter((item) => item.problem_id !== row.problem_id)
  detail.value = { ...detail.value, items }
  void persistItems(items)
}

/** 上移 / 下移与拖拽共用：整体重排后落库 */
function reorderItems(from: number, to: number): void {
  if (!detail.value || arranging.value) return
  if (from === to || from < 0 || to < 0 || to >= detail.value.items.length) return
  const items = [...detail.value.items]
  const [moved] = items.splice(from, 1)
  if (!moved) return
  items.splice(to, 0, moved)
  const next = items.map((item, index) => ({ ...item, sort_order: index }))
  detail.value = { ...detail.value, items: next }
  void persistItems(next)
}

function moveItem(index: number, delta: number): void {
  if (!detail.value) return
  const target = index + delta
  if (target < 0 || target >= detail.value.items.length) return
  reorderItems(index, target)
}

function goEdit(): void {
  router.push(`/admin/problem-sets/${setId.value}/edit`)
}

function doArchive(): void {
  confirmAsyncDialog({
    title: t('problemSets.detail.archive'),
    content: t('problemSets.detail.archiveConfirm'),
    positiveText: t('problemSets.detail.archive'),
    danger: true,
    action: () =>
      teamId.value
        ? archiveTeamProblemSet(teamId.value, setId.value)
        : archiveProblemSet(setId.value),
    successMessage: t('common.success'),
    onAfterSuccess: () => {
      router.push(teamId.value ? `/teams/${teamId.value}` : '/admin/problem-sets')
    },
  })
}

async function loadArrangeable(query: {
  page: number
  page_size: number
  keyword?: string
}): Promise<PageResult<ProblemSummary>> {
  const result = await searchTeamArrangeableProblems(teamId.value!, {
    page: query.page,
    page_size: query.page_size,
    keyword: query.keyword,
  })
  return result
}

const chosenIds = computed(
  () => new Set((detail.value?.items ?? []).map((item) => item.problem_id)),
)
const canArrange = computed(() => detail.value?.status === 'active' && !arranging.value)
</script>

<template>
  <WorkbenchShell>
    <template #title>
      <div class="flex flex-wrap items-center gap-2">
        <h1 class="truncate text-xl font-semibold leading-tight tracking-tight">
          {{ detail?.title ?? t('problemSets.detail.arrangeTitle') }}
        </h1>
        <ProblemSetVisibilityBadge v-if="detail" :visibility="detail.visibility" />
        <ToneBadge
          v-if="detail?.status === 'archived'"
          tone="warning"
          :label="t('problemSets.detail.archived')"
        />
      </div>
    </template>

    <template #actions>
      <template v-if="detail">
        <Button v-if="!teamId" variant="outline" size="sm" @click="goEdit">
          {{ t('problemSets.detail.edit') }}
        </Button>
        <Button
          v-if="detail.status === 'active'"
          variant="destructive"
          size="sm"
          @click="doArchive"
        >
          {{ t('problemSets.detail.archive') }}
        </Button>
      </template>
      <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
    </template>

    <div v-if="loading && !detail" class="grid min-h-0 flex-1 place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <div
      v-else-if="detail"
      class="grid min-h-0 flex-1 gap-4 overflow-y-auto lg:grid-cols-[minmax(0,4fr)_minmax(0,8fr)] lg:overflow-hidden"
    >
      <!-- 左框：题单介绍（内部滚动） -->
      <section
        class="flex min-h-[280px] flex-col overflow-hidden rounded-xl border border-border bg-card lg:min-h-0"
      >
        <header class="shrink-0 border-b border-border/70 px-4 py-2.5 text-[13px] font-semibold">
          {{ t('problemSets.list.descLabel') }}
        </header>
        <div class="min-h-0 flex-1 overflow-y-auto px-4 py-3">
          <MarkdownView v-if="detail.description" :source="detail.description" />
          <div v-else class="flex h-full min-h-[220px] items-center justify-center">
            <EmptyState :text="t('problemSets.detail.noDescription')" />
          </div>
        </div>
      </section>

      <!-- 右框：题目列表（点进来即编排，表体内部滚动） -->
      <section
        class="flex min-h-[340px] flex-col overflow-hidden rounded-xl border border-border bg-card lg:min-h-0"
      >
        <header
          class="flex shrink-0 items-center justify-between gap-2 border-b border-border/70 px-4 py-2"
        >
          <span class="flex items-center gap-2 text-[13px] font-semibold">
            {{ t('problemSets.detail.problems') }} · {{ detail.items.length }}
            <Loader2 v-if="arranging" class="size-3.5 animate-spin text-muted-foreground" />
          </span>
          <Button size="sm" :disabled="!canArrange" @click="pickerShow = true">
            <Plus class="size-3.5" />
            {{ t('problemSets.form.pickAdd') }}
          </Button>
        </header>
        <div class="min-h-0 flex-1 overflow-auto">
          <ProblemSetArrangeTable
            :items="detail.items"
            :disabled="!canArrange"
            :empty-text="t('problemSets.detail.empty')"
            @move="moveItem"
            @remove="removeItem"
            @reorder="reorderItems"
          />
        </div>
      </section>
    </div>

    <ProblemPicker
      v-model:show="pickerShow"
      :chosen-ids="chosenIds"
      :loader="teamId ? loadArrangeable : undefined"
      @add="onPicked"
    />
  </WorkbenchShell>
</template>
