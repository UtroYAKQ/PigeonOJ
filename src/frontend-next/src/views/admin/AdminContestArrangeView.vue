<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useDebounceFn } from '@vueuse/core'
import { ArrowDown, ArrowUp, Loader2, Plus, Search, Trash } from '@lucide/vue'

import { getContest, searchContestProblems, updateContest } from '@/api/contests'
import { getTeamContest, searchTeamContestProblems, updateTeamContest } from '@/api/teams'
import LineList from '@/components/common/LineList.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { message } from '@/utils/feedback'
import type { ContestProblemItem } from '@/types'

interface PoolCandidate {
  problem_id: string
  title: string
  difficulty: number | null
}

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const contestId = computed(() => String(route.params.cid))
const teamId = computed(() => (route.params.teamId ? String(route.params.teamId) : null))
const listPath = computed(() => (teamId.value ? `/teams/${teamId.value}` : '/admin/contests'))
const basicPath = computed(() =>
  teamId.value
    ? `/teams/${teamId.value}/contests/${contestId.value}/edit/basic`
    : `/admin/contests/${contestId.value}/edit/basic`,
)

const loading = ref(false)
const saving = ref(false)
const contestTitle = ref('')
/** IOI 赛制才需要逐题分值（ACM 全部测试点通过才有分，无单题分值概念） */
const isIOI = ref(false)
const draftProblems = ref<ContestProblemItem[]>([])

const poolKeyword = ref('')
const poolLoading = ref(false)
const poolOptions = ref<PoolCandidate[]>([])

function contestDetail() {
  return teamId.value ? getTeamContest(teamId.value, contestId.value) : getContest(contestId.value)
}

onMounted(async () => {
  loading.value = true
  try {
    const detail = await contestDetail()
    contestTitle.value = detail.title
    isIOI.value = detail.rule_type === 'IOI'
    draftProblems.value = detail.problems.map((item) => ({ ...item }))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
    void router.push(listPath.value)
    return
  } finally {
    loading.value = false
  }
  void searchPool('')
})

async function searchPool(keyword: string): Promise<void> {
  poolLoading.value = true
  try {
    // 编排专属搜索：公开题 + 本人私有题（已发布），排除已在列表中的
    const query = { page: 1, page_size: 20, keyword: keyword || undefined }
    const result = await (teamId.value
      ? searchTeamContestProblems(teamId.value, contestId.value, query)
      : searchContestProblems(contestId.value, query))
    const chosen = new Set(draftProblems.value.map((item) => item.problem_id))
    poolOptions.value = result.items
      .filter((item) => !chosen.has(item.problem_id))
      .map((item) => ({
        problem_id: item.problem_id,
        title: item.title,
        difficulty: item.difficulty ?? null,
      }))
  } catch {
    poolOptions.value = []
  } finally {
    poolLoading.value = false
  }
}

const debouncedPoolSearch = useDebounceFn(() => {
  void searchPool(poolKeyword.value)
}, 300)

watch(poolKeyword, () => {
  debouncedPoolSearch()
})

function addFromPool(item: PoolCandidate): void {
  draftProblems.value.push({
    problem_id: item.problem_id,
    letter: null,
    // IOI 未填分值默认 100（后端 _replace_problems 同款兜底，docs/contracts/contests.md）
    score: isIOI.value ? 100 : 0,
    sort_order: draftProblems.value.length,
    title: item.title,
    difficulty: item.difficulty,
  })
  poolOptions.value = poolOptions.value.filter((option) => option.problem_id !== item.problem_id)
}

function removeDraft(item: ContestProblemItem): void {
  draftProblems.value = draftProblems.value.filter((row) => row.problem_id !== item.problem_id)
  // 移出后立即可在候选中重新选回（旧实现需重新搜索才能看到）
  void searchPool(poolKeyword.value)
}

function moveDraft(index: number, delta: number): void {
  const target = index + delta
  if (target < 0 || target >= draftProblems.value.length) return
  const items = [...draftProblems.value]
  ;[items[index], items[target]] = [items[target]!, items[index]!]
  draftProblems.value = items.map((item, order) => ({ ...item, sort_order: order }))
}

function letter(index: number): string {
  return String.fromCharCode(65 + index)
}

function setScore(item: ContestProblemItem, value: string | number): void {
  item.score = Math.max(0, Number(value) || 0)
}

/** 保存编排：problems 全量替换；成功后回比赛管理列表 */
async function save(): Promise<void> {
  if (saving.value) return
  saving.value = true
  try {
    const payload = {
      problems: draftProblems.value.map((item) => ({
        problem_id: item.problem_id,
        score: item.score,
      })),
    }
    await (teamId.value
      ? updateTeamContest(teamId.value, contestId.value, payload)
      : updateContest(contestId.value, payload))
    message.success(t('common.success'))
    void router.push(listPath.value)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    saving.value = false
  }
}

function goPrev(): void {
  void router.push(basicPath.value)
}
</script>

<template>
  <div class="mx-auto w-full max-w-[1200px] px-4 pb-12 pt-4 sm:px-6">
    <header class="flex flex-wrap items-center gap-2">
      <h1 class="text-xl font-semibold leading-tight tracking-tight">
        {{ t('contests.wizard.arrange') }}
      </h1>
      <span class="text-[12px] font-medium text-muted-foreground">2 / 2</span>
    </header>

    <div v-if="loading" class="grid min-h-[420px] place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <!-- 与基本信息页一致：无框分区 + 细分隔线 + 列表行分隔 -->
    <div v-else class="mt-5">
      <h2 class="text-lg font-medium">{{ t('contests.list.problems') }}</h2>
      <p v-if="contestTitle" class="mt-1 truncate text-sm text-muted-foreground">
        {{ contestTitle }}
      </p>
      <div class="my-5 h-px bg-border" role="separator" />

      <div class="grid gap-8 lg:grid-cols-[1.15fr_1fr]">
        <section class="flex max-h-[560px] min-h-[360px] flex-col gap-3">
          <div class="flex items-center justify-between gap-2">
            <h3 class="text-sm font-medium">{{ t('contests.list.problems') }}</h3>
            <span class="text-[12px] tabular-nums text-muted-foreground">
              {{ t('contests.list.problemCount', { count: draftProblems.length }) }}
            </span>
          </div>

          <LineList
            :items="draftProblems"
            :empty-text="t('contests.list.problemsEmpty')"
            :get-key="(item: ContestProblemItem) => item.problem_id"
            class="pr-0.5"
          >
            <template #item="{ item, index }">
              <div class="flex items-center gap-2 py-2">
                <span
                  class="grid size-6 shrink-0 place-items-center rounded bg-muted text-[12px] font-semibold text-muted-foreground"
                >
                  {{ letter(index) }}
                </span>
                <Input
                  v-if="isIOI"
                  :model-value="item.score"
                  type="number"
                  min="0"
                  class="h-8 w-[76px] text-sm"
                  :aria-label="t('contests.list.problemScore')"
                  @update:model-value="(value) => setScore(item, value)"
                />
                <span class="min-w-0 flex-1 truncate text-sm">{{ item.title }}</span>
                <span
                  v-if="item.difficulty != null"
                  class="shrink-0 text-[12px] tabular-nums text-muted-foreground"
                >
                  {{ item.difficulty }}
                </span>
                <div class="flex shrink-0 items-center gap-0.5">
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    :disabled="index === 0"
                    :aria-label="t('action.moveUp')"
                    @click="moveDraft(index, -1)"
                  >
                    <ArrowUp class="size-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    :disabled="index === draftProblems.length - 1"
                    :aria-label="t('action.moveDown')"
                    @click="moveDraft(index, 1)"
                  >
                    <ArrowDown class="size-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    class="text-muted-foreground hover:text-destructive"
                    :aria-label="t('contests.list.removeProblem')"
                    @click="removeDraft(item)"
                  >
                    <Trash class="size-3.5" />
                  </Button>
                </div>
              </div>
            </template>
          </LineList>
        </section>

        <section class="flex max-h-[560px] min-h-[360px] flex-col gap-3">
          <div class="flex items-center justify-between gap-2">
            <h3 class="text-sm font-medium">{{ t('contests.list.pickProblem') }}</h3>
            <Loader2 v-if="poolLoading" class="size-3.5 animate-spin text-muted-foreground" />
          </div>

          <div class="relative">
            <Search
              class="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              :model-value="poolKeyword"
              class="h-10 pl-9 text-sm"
              :placeholder="t('contests.list.pickProblem')"
              @update:model-value="(value) => (poolKeyword = String(value))"
              @keyup.enter="searchPool(poolKeyword)"
            />
          </div>

          <LineList
            :items="poolOptions"
            :empty-text="t('contests.detail.noResult')"
            :get-key="(item: PoolCandidate) => item.problem_id"
          >
            <template #item="{ item }">
              <button
                type="button"
                class="flex w-full items-center gap-2 px-1 py-2 text-left transition-colors hover:bg-muted/60"
                @click="addFromPool(item)"
              >
                <span class="min-w-0 flex-1 truncate text-sm">{{ item.title }}</span>
                <span
                  v-if="item.difficulty != null"
                  class="shrink-0 text-[12px] tabular-nums text-muted-foreground"
                >
                  {{ item.difficulty }}
                </span>
                <Plus class="size-4 shrink-0 text-muted-foreground" />
              </button>
            </template>
          </LineList>
        </section>
      </div>

      <div class="mt-8 flex flex-wrap justify-start gap-2">
        <Button type="button" :disabled="saving" @click="save">
          <Loader2 v-if="saving" class="size-4 animate-spin" />
          {{ t('action.save') }}
        </Button>
        <Button type="button" variant="outline" @click="goPrev">
          {{ t('contests.wizard.prev') }}
        </Button>
      </div>
    </div>
  </div>
</template>
