<script setup lang="ts">
import { computed, h, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { DataTableColumns } from 'naive-ui'

import { createSubmission, listSubmissions } from '@/api/judge'
import { getProblem } from '@/api/problems'
import { dialog, message } from '@/utils/feedback'
import { useSplitPane } from '@/composables/useSplitPane'
import { languageOptions } from '@/constants/languages'
import CodeEditor from '@/components/CodeEditor.vue'
import StatusTag from '@/components/StatusTag.vue'
import ProblemMetaBar from '@/components/problem/ProblemMetaBar.vue'
import ProblemStatement from '@/components/problem/ProblemStatement.vue'
import type { ProblemDetailEx, ProblemLanguage, Submission } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const problem = ref<ProblemDetailEx | null>(null)
const loading = ref(false)
const submitting = ref(false)
const subsVisible = ref(false)
const language = ref<ProblemLanguage>('cpp17')
const mySubmissions = ref<Submission[]>([])

const code = ref('')

const { isDesktop, splitRef, layoutStyle, startResize, resetSplit, updateSplitHeight } =
  useSplitPane()

async function load() {
  loading.value = true
  try {
    problem.value = await getProblem(String(route.params.id))
    await loadMySubmissions()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
  } finally {
    loading.value = false
  }
}
async function loadMySubmissions() {
  try {
    const result = await listSubmissions({ problem_id: String(route.params.id), page_size: 5 })
    mySubmissions.value = result.items
  } catch {
    /* 未登录等场景静默 */
  }
}

function openSubmission(row: Submission) {
  subsVisible.value = false
  router.push(`/problems/${route.params.id}/submissions/${row.id}`)
}

async function submit() {
  if (!problem.value || submitting.value) return
  dialog.warning({
    title: t('problems.detail.submit'),
    content: t('problems.detail.submitConfirm'),
    positiveText: t('problems.detail.submit'),
    negativeText: t('action.cancel'),
    onPositiveClick: async () => {
      submitting.value = true
      try {
        const result = await createSubmission({
          problem_id: problem.value!.id,
          language: language.value,
          code: code.value,
        })
        router.push(`/problems/${problem.value!.id}/submissions/${result.submission_id}`)
      } catch (error) {
        message.error(error instanceof Error ? error.message : t('problems.detail.submitFailed'))
      } finally {
        submitting.value = false
      }
    },
  })
}

onMounted(load)
watch(problem, () => nextTick(updateSplitHeight))

const submissionColumns = computed<DataTableColumns<Submission>>(() => [
  {
    title: t('problems.detail.status'),
    key: 'status',
    minWidth: 150,
    render: (row) => h(StatusTag, { status: row.status }),
  },
  { title: t('problems.submission.score'), key: 'score', width: 80 },
  {
    title: t('problems.submission.time'),
    key: 'time',
    width: 110,
    render: (row) => `${row.time_used_ms ?? '-'} ms`,
  },
  { title: t('problems.detail.language'), key: 'language', width: 120 },
])
</script>

<template>
  <div class="problem-detail">
    <div
      v-if="problem"
      ref="splitRef"
      class="problem-detail__layout"
      :class="{ stacked: !isDesktop }"
      :style="layoutStyle"
    >
      <!-- 左栏：题面（独立滚动） -->
      <section class="problem-detail__statement">
        <n-card :bordered="false" class="statement-card" content-style="padding: 20px;">
          <template #header>
            <ProblemMetaBar :problem="problem" show-title hide-published-status />
          </template>

          <ProblemStatement :problem="problem" />
        </n-card>
      </section>

      <!-- 可拖拽分隔条 -->
      <div
        class="problem-detail__divider"
        role="separator"
        aria-orientation="vertical"
        :aria-label="t('problems.detail.resizeHint')"
        :title="t('problems.detail.resizeHint')"
        @pointerdown="startResize"
        @dblclick="resetSplit"
      />

      <!-- 右栏：编辑器（提交历史收进工具栏按钮） -->
      <section class="problem-detail__workbench">
        <div class="editor-shell">
          <div class="editor-toolbar">
            <n-select
              v-model:value="language"
              class="editor-toolbar__language"
              :options="languageOptions"
            />
            <div class="editor-toolbar__actions">
              <n-button secondary @click="subsVisible = true">{{
                t('problems.detail.mySubmissions')
              }}</n-button>
              <n-button type="primary" :loading="submitting" @click="submit">{{
                t('problems.detail.submit')
              }}</n-button>
            </div>
          </div>
          <div class="editor-wrap">
            <CodeEditor v-model="code" :language="language" />
          </div>
        </div>
      </section>
    </div>

    <!-- 提交历史弹窗 -->
    <n-modal
      v-model:show="subsVisible"
      preset="card"
      :title="t('problems.detail.mySubmissions')"
      style="width: min(720px, 92vw)"
    >
      <n-data-table
        v-if="mySubmissions.length"
        size="small"
        :columns="submissionColumns"
        :data="mySubmissions"
        :row-props="(row: Submission) => ({ style: 'cursor: pointer;', onClick: () => openSubmission(row) })"
      />
      <n-empty v-else :description="t('problems.detail.noSubmissions')" />
    </n-modal>
  </div>
</template>

<style scoped>
.problem-detail__layout {
  display: grid;
  grid-template-columns: minmax(300px, var(--split, 50%)) auto minmax(360px, 1fr);
  align-items: stretch;
  gap: 4px;
  /* 高度锁定为一屏（顶栏 60px + 内容区上下内边距 28px）：
     题面过长时左栏内部滚动，不再把整页撑高 */
  height: calc(100dvh - 88px);
}
.problem-detail__statement {
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  min-height: 0;
  padding-right: 6px;
}
.statement-card {
  flex: 1;
}

.problem-detail__divider {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  margin: 0 -3px;
  cursor: col-resize;
  touch-action: none;
  z-index: 2;
}
.problem-detail__divider::before {
  content: '';
  width: 4px;
  height: 56px;
  border-radius: var(--app-radius-sm, 4px);
  background: var(--app-border);
  /* 功能性分隔条：仅背景色反馈，无尺寸/位移动画 */
  transition: background-color 0.15s ease;
}
.problem-detail__divider:hover::before,
.problem-detail__divider:focus-visible::before {
  background: var(--app-primary);
}

.problem-detail__workbench {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
  min-height: 0;
}
.editor-shell {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 260px;
}
.editor-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.editor-toolbar__language {
  width: 150px;
}
.editor-toolbar__actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
.editor-wrap {
  flex: 1;
  min-height: 0;
}

@media (max-width: 899px) {
  .problem-detail__layout.stacked {
    display: block;
    height: auto; /* 堆叠时按内容自然高度，整页滚动 */
  }
  .problem-detail__statement {
    overflow: visible;
    padding-right: 0;
  }
  .problem-detail__divider {
    display: none;
  }
  .editor-shell {
    min-height: 480px;
  }
}
</style>
