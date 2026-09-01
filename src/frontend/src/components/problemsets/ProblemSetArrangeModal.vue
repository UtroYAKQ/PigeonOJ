<script setup lang="ts">
/**
 * 题单编排题目弹窗（管理后台共享：题单管理列表 / 题单详情页共用）。
 * 左侧目标列表（增删排序），右侧题库搜索添加；保存为全量替换（docs/contracts/problem-sets.md）。
 */
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import ModalFooter from '@/components/ModalFooter.vue'
import { getProblemSet, replaceProblemSetItems } from '@/api/problemSets'
import { listProblems } from '@/api/problems'
import { message } from '@/utils/feedback'
import type { PageResult, ProblemSetItem, ProblemSetSummary, ProblemSummary } from '@/types'

const props = defineProps<{
  show: boolean
  problemSet: ProblemSetSummary | null
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  saved: []
}>()

const { t } = useI18n()
const saving = ref(false)
/** 待保存的目标列表（行内增删排序，保存时全量提交） */
const draftItems = ref<ProblemSetItem[]>([])
/** 题库搜索：从已发布公开题目中选择 */
const poolKeyword = ref('')
const poolLoading = ref(false)
const poolOptions = ref<Array<{ label: string; value: string; problem: ProblemSummary }>>([])

watch(
  () => props.show,
  async (show) => {
    if (!show || !props.problemSet) return
    try {
      const detail = await getProblemSet(props.problemSet.id)
      draftItems.value = detail.items.map((it) => ({ ...it }))
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('common.loadFailed'))
      return
    }
    poolKeyword.value = ''
    poolOptions.value = []
    searchPool('')
  },
)

async function searchPool(keyword: string) {
  poolLoading.value = true
  try {
    const result: PageResult<ProblemSummary> = await listProblems({
      page: 1,
      page_size: 20,
      keyword: keyword || undefined,
    })
    const chosen = new Set(draftItems.value.map((it) => it.problem_id))
    poolOptions.value = result.items
      .filter((p) => !chosen.has(p.id))
      .map((p) => ({ label: p.title, value: p.id, problem: p }))
  } catch {
    poolOptions.value = []
  } finally {
    poolLoading.value = false
  }
}

function addFromPool(problem: ProblemSummary) {
  draftItems.value.push({
    problem_id: problem.id,
    title: problem.title,
    difficulty: problem.difficulty ?? null,
    sort_order: draftItems.value.length,
  })
  poolOptions.value = poolOptions.value.filter((o) => o.value !== problem.id)
}

function removeDraft(row: ProblemSetItem) {
  draftItems.value = draftItems.value.filter((it) => it.problem_id !== row.problem_id)
}

function moveDraft(index: number, delta: number) {
  const target = index + delta
  if (target < 0 || target >= draftItems.value.length) return
  const items = [...draftItems.value]
  ;[items[index], items[target]] = [items[target], items[index]]
  draftItems.value = items.map((it, i) => ({ ...it, sort_order: i }))
}

async function submitArrange() {
  if (!props.problemSet) return
  saving.value = true
  try {
    await replaceProblemSetItems(props.problemSet.id, {
      items: draftItems.value.map((it, i) => ({ problem_id: it.problem_id, sort_order: i })),
    })
    emit('update:show', false)
    message.success(t('common.success'))
    emit('saved')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    style="width: min(760px, 94vw)"
    :title="t('problemSets.detail.arrangeTitle')"
    @update:show="emit('update:show', $event)"
  >
    <div class="arrange">
      <div class="arrange__list">
        <div v-for="(item, index) in draftItems" :key="item.problem_id" class="arrange__row">
          <span class="arrange__order">{{ index + 1 }}</span>
          <span class="arrange__title">{{ item.title }}</span>
          <span class="arrange__ops">
            <n-button text size="tiny" aria-label="up" @click="moveDraft(index, -1)">↑</n-button>
            <n-button text size="tiny" aria-label="down" @click="moveDraft(index, 1)">↓</n-button>
            <n-button text size="tiny" type="error" @click="removeDraft(item)">
              {{ t('problemSets.detail.remove') }}
            </n-button>
          </span>
        </div>
        <n-empty v-if="!draftItems.length" :description="t('problemSets.detail.empty')" />
      </div>
      <div class="arrange__pool">
        <n-input
          v-model:value="poolKeyword"
          :placeholder="t('problemSets.detail.pickProblem')"
          clearable
          @update:value="searchPool"
        />
        <span v-if="!poolOptions.length && !poolLoading" class="arrange__noresult">
          {{ t('problemSets.detail.noResult') }}
        </span>
        <div v-else class="arrange__results">
          <n-button
            v-for="opt in poolOptions"
            :key="opt.value"
            secondary
            size="small"
            class="arrange__result"
            @click="addFromPool(opt.problem)"
          >
            {{ opt.label }}
          </n-button>
        </div>
      </div>
    </div>
    <template #footer>
      <ModalFooter
        :loading="saving"
        @cancel="emit('update:show', false)"
        @confirm="submitArrange"
      />
    </template>
  </n-modal>
</template>

<style scoped>
.arrange {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 16px;
}
.arrange__list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 420px;
  overflow: auto;
}
.arrange__row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid var(--app-border);
  border-radius: 3px;
}
.arrange__order {
  width: 20px;
  color: var(--app-text-secondary);
  font-size: 12px;
}
.arrange__title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.arrange__ops {
  display: inline-flex;
  gap: 2px;
}
.arrange__pool {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.arrange__results {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 380px;
  overflow: auto;
  align-items: stretch;
}
.arrange__result {
  justify-content: flex-start;
}
.arrange__noresult {
  color: var(--app-text-secondary);
  font-size: 12px;
}
@media (max-width: 900px) {
  .arrange {
    grid-template-columns: 1fr;
  }
}
</style>
