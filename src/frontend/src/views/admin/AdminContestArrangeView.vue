<script setup lang="ts">
/**
 * 比赛向导 · 步骤 2 编排题目（题号自动分配、IOI 分值、顺序调整）。
 * 路由：/admin/contests/:cid/edit/problems（编辑与新建第二步骤共用）。
 * 保存 = PUT /contests/{id} problems 全量替换（后端重排字母 A/B/C…）。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { getContest, searchContestProblems, updateContest } from '@/api/contests'
import { message } from '@/utils/feedback'
import WizardShell from '@/components/WizardShell.vue'
import type { ContestProblemItem } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const contestId = computed(() => String(route.params.cid))
const loading = ref(false)
const saving = ref(false)
const contestTitle = ref('')

const draftProblems = ref<ContestProblemItem[]>([])
const poolKeyword = ref('')
const poolLoading = ref(false)
const poolOptions = ref<
  Array<{
    label: string
    value: string
    problem: { id: string; title: string; difficulty: number | null }
  }>
>([])
/** IOI 赛制才需要逐题分值（ACM 全部测试点通过才有分，无单题分值概念） */
const isIOI = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const detail = await getContest(contestId.value)
    contestTitle.value = detail.title
    isIOI.value = detail.rule_type === 'IOI'
    draftProblems.value = detail.problems.map((it) => ({ ...it }))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
    router.push('/admin/contests')
  } finally {
    loading.value = false
  }
  void searchPool('')
})

async function searchPool(keyword: string) {
  poolLoading.value = true
  try {
    // 编排专属搜索：公开题 + 本人私有题（已发布），排除已在列表中的
    const result = await searchContestProblems(contestId.value, {
      page: 1,
      page_size: 20,
      keyword: keyword || undefined,
    })
    const chosen = new Set(draftProblems.value.map((it) => it.problem_id))
    poolOptions.value = result.items
      .filter((p) => !chosen.has(p.problem_id))
      .map((p) => ({
        label: p.title,
        value: p.problem_id,
        problem: { id: p.problem_id, title: p.title, difficulty: p.difficulty ?? null },
      }))
  } catch {
    poolOptions.value = []
  } finally {
    poolLoading.value = false
  }
}

function addFromPool(problem: { id: string; title: string; difficulty: number | null }) {
  draftProblems.value.push({
    problem_id: problem.id,
    letter: null,
    score: 0,
    sort_order: draftProblems.value.length,
    title: problem.title,
    difficulty: problem.difficulty ?? null,
  })
  poolOptions.value = poolOptions.value.filter((o) => o.value !== problem.id)
}

function removeDraft(row: ContestProblemItem) {
  draftProblems.value = draftProblems.value.filter((it) => it.problem_id !== row.problem_id)
}

function moveDraft(index: number, delta: number) {
  const target = index + delta
  if (target < 0 || target >= draftProblems.value.length) return
  const items = [...draftProblems.value]
  ;[items[index], items[target]] = [items[target], items[index]]
  draftProblems.value = items.map((it, i) => ({ ...it, sort_order: i }))
}

/** 保存编排：problems 全量替换；成功后回比赛管理列表 */
async function save() {
  saving.value = true
  try {
    await updateContest(contestId.value, {
      problems: draftProblems.value.map((it) => ({
        problem_id: it.problem_id,
        score: it.score,
      })),
    })
    message.success(t('common.success'))
    router.push('/admin/contests')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    saving.value = false
  }
}

function goPrev() {
  router.push(`/admin/contests/${contestId.value}/edit/basic`)
}
</script>

<template>
  <div class="page-fill">
    <n-spin :show="loading" class="wizard-spin">
      <WizardShell :step="2" :total="2" :title="t('contests.wizard.arrange')">
        <template #actions>
          <n-button size="small" quaternary @click="goPrev">{{
            t('contests.wizard.prev')
          }}</n-button>
          <n-button type="primary" size="small" :loading="saving" @click="save">
            {{ t('action.save') }}
          </n-button>
        </template>

        <p v-if="contestTitle" class="arrange-page__contest">
          {{ contestTitle }}
        </p>
        <div class="arrange-page">
          <div class="arrange-page__panel">
            <div class="arrange-page__panel-title">{{ t('contests.list.problems') }}</div>
            <div class="arrange-page__list">
              <div
                v-for="(item, index) in draftProblems"
                :key="item.problem_id"
                class="arrange__row"
              >
                <span class="arrange__order">{{ String.fromCharCode(65 + index) }}</span>
                <n-input-number
                  v-if="isIOI"
                  :value="item.score"
                  size="tiny"
                  :min="0"
                  style="width: 90px"
                  :show-button="false"
                  @update:value="
                    (v: number | null) => {
                      item.score = v ?? 0
                    }
                  "
                />
                <span class="arrange__title">{{ item.title }}</span>
                <span class="arrange__ops">
                  <n-button text size="tiny" aria-label="up" @click="moveDraft(index, -1)"
                    >↑</n-button
                  >
                  <n-button text size="tiny" aria-label="down" @click="moveDraft(index, 1)"
                    >↓</n-button
                  >
                  <n-button text size="tiny" type="error" @click="removeDraft(item)">
                    {{ t('contests.list.removeProblem') }}
                  </n-button>
                </span>
              </div>
              <n-empty
                v-if="!draftProblems.length"
                :description="t('contests.list.problemsEmpty')"
              />
            </div>
          </div>
          <div class="arrange-page__panel">
            <div class="arrange-page__panel-title">{{ t('contests.list.pickProblem') }}</div>
            <n-input
              v-model:value="poolKeyword"
              :placeholder="t('contests.list.pickProblem')"
              clearable
              @update:value="searchPool"
            />
            <div v-if="poolOptions.length" class="arrange-page__results">
              <n-button
                v-for="opt in poolOptions"
                :key="opt.value"
                secondary
                size="small"
                class="arrange-page__result"
                @click="addFromPool(opt.problem)"
              >
                {{ opt.label }}
              </n-button>
            </div>
            <span v-else class="arrange-page__noresult">{{ t('contests.detail.noResult') }}</span>
          </div>
        </div>
      </WizardShell>
    </n-spin>
  </div>
</template>

<style scoped>
/* page-fill 高度链：spin 与卡片逐层吃满，壳到底、内容区内部滚动 */
.wizard-spin {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.wizard-spin :deep(.n-spin-container),
.wizard-spin :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.wizard-spin :deep(.n-card) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.wizard-spin :deep(.n-card-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.arrange-page__contest {
  margin: 0 0 12px;
  color: var(--app-text-secondary);
  font-size: 13px;
  flex-shrink: 0;
}
.arrange-page {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: 16px;
  flex: 1;
  min-height: 0;
}
/* 左右两栏各成面板：边框 + 面板标题，视觉上把「已编排」与「题库候选」分开；
   高度吃满剩余空间（全局铺满），列表内部滚动 */
.arrange-page__panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  background: var(--app-card-bg, #fff);
  min-height: 0;
}
.arrange-page__panel-title {
  font-size: 13px;
  font-weight: 650;
  color: var(--app-text);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.arrange-page__panel-title::before {
  content: '';
  width: 3px;
  height: 13px;
  border-radius: 2px;
  background: var(--app-primary);
  flex-shrink: 0;
}
.arrange-page__list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow: auto;
  flex: 1;
  min-height: 0;
}
.arrange__row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border: 1px solid var(--app-border);
  border-radius: 6px;
}
.arrange__order {
  width: 24px;
  color: var(--app-primary);
  font-weight: 650;
  font-size: 13px;
}
.arrange__title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
.arrange__ops {
  display: inline-flex;
  gap: 2px;
}
.arrange-page__pool {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.arrange-page__results {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow: auto;
  flex: 1;
  align-items: stretch;
}
.arrange-page__result {
  justify-content: flex-start;
}
.arrange-page__noresult {
  color: var(--app-text-secondary);
  font-size: 12px;
}
@media (max-width: 900px) {
  .arrange-page {
    grid-template-columns: 1fr;
  }
}
</style>
