<script setup lang="ts">
/**
 * 写题工作台大组件：左栏题面卡片 + 可拖拽分隔条 + 右栏编辑器工具行。
 * 工具行按钮只抛事件、行为由宿主页面注入——普通做题传 @submit 走正式提交，
 * 验题页传 @submit 走自行验题提交，保证各页面工具行外观完全一致。
 * 分栏比例全局持久化（useSplitPane），窄屏（<900px）自动上下堆叠。
 */
import { nextTick, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSplitPane } from '@/composables/useSplitPane'
import { languageOptions } from '@/constants/languages'
import CodeEditor from '@/components/CodeEditor.vue'
import ProblemMetaBar from '@/components/problem/ProblemMetaBar.vue'
import ProblemStatement from '@/components/problem/ProblemStatement.vue'
import type { ProblemDetailEx, ProblemLanguage } from '@/types'

const props = withDefaults(
  defineProps<{
    /** 题目详情（题面 + 元信息） */
    problem: ProblemDetailEx
    /** 主按钮 loading（提交中） */
    submitting?: boolean
    /** 主按钮禁用（如验题代码为空） */
    submitDisabled?: boolean
    /** 是否渲染官方题解分区 */
    showSolution?: boolean
    /** 已发布时隐藏状态标签（前台消费页口径） */
    hidePublishedStatus?: boolean
  }>(),
  { showSolution: true },
)

const emit = defineEmits<{
  /** 主提交动作：普通做题 / 自行验题由宿主决定 */
  submit: []
  /** 打开本人该题的提交记录 */
  'show-submissions': []
}>()

const code = defineModel<string>('code', { required: true })
const language = defineModel<ProblemLanguage>('language', { required: true })

const { t } = useI18n()

// 分栏拖拽与高度实测由 useSplitPane 提供；题目数据就位后重测一次可用高度
const { isDesktop, splitRef, layoutStyle, startResize, resetSplit, updateSplitHeight } =
  useSplitPane()

onMounted(updateSplitHeight)
watch(
  () => props.problem,
  () => nextTick(updateSplitHeight),
)
</script>

<template>
  <div
    ref="splitRef"
    class="problem-workbench"
    :class="{ stacked: !isDesktop }"
    :style="layoutStyle"
  >
    <!-- 左栏：题面（独立滚动） -->
    <section class="problem-workbench__statement">
      <n-card :bordered="false" class="statement-card" content-style="padding: 20px;">
        <template #header>
          <ProblemMetaBar
            :problem="problem"
            show-title
            :hide-published-status="hidePublishedStatus"
          />
        </template>

        <ProblemStatement :problem="problem" :show-solution="showSolution" />
      </n-card>
    </section>

    <!-- 可拖拽分隔条 -->
    <div
      class="problem-workbench__divider"
      role="separator"
      aria-orientation="vertical"
      :aria-label="t('problems.detail.resizeHint')"
      :title="t('problems.detail.resizeHint')"
      @pointerdown="startResize"
      @dblclick="resetSplit"
    />

    <!-- 右栏：编辑器工作台（提交历史收进工具栏按钮） -->
    <section class="problem-workbench__editor">
      <div class="editor-shell">
        <div class="editor-toolbar">
          <n-select
            v-model:value="language"
            class="editor-toolbar__language"
            :options="languageOptions"
          />
          <div class="editor-toolbar__actions">
            <n-button secondary @click="emit('show-submissions')">{{
              t('problems.detail.mySubmissions')
            }}</n-button>
            <n-button
              type="primary"
              :loading="submitting"
              :disabled="submitDisabled"
              @click="emit('submit')"
              >{{ t('problems.detail.submit') }}</n-button
            >
          </div>
        </div>
        <div class="editor-wrap">
          <CodeEditor v-model="code" :language="language" />
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.problem-workbench {
  display: grid;
  grid-template-columns: minmax(300px, var(--split, 50%)) auto minmax(360px, 1fr);
  align-items: stretch;
  gap: 4px;
  /* 高度兜底口径（对齐详情页一屏锁定）：挂载后由 useSplitPane 实测剩余高度以内联样式覆盖 */
  height: calc(100dvh - 88px);
}
.problem-workbench__statement {
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  min-height: 0;
  padding-right: 6px;
}
.statement-card {
  flex: 1;
}

.problem-workbench__divider {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  margin: 0 -3px;
  cursor: col-resize;
  touch-action: none;
  z-index: 2;
}
.problem-workbench__divider::before {
  content: '';
  width: 4px;
  height: 56px;
  border-radius: var(--app-radius-sm, 4px);
  background: var(--app-border);
  /* 功能性分隔条：仅背景色反馈，无尺寸/位移动画 */
  transition: background-color 0.15s ease;
}
.problem-workbench__divider:hover::before,
.problem-workbench__divider:focus-visible::before {
  background: var(--app-primary);
}

.problem-workbench__editor {
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
  .problem-workbench.stacked {
    display: block;
    height: auto; /* 堆叠时按内容自然高度，整页滚动 */
  }
  .problem-workbench__statement {
    overflow: visible;
    padding-right: 0;
  }
  .problem-workbench__divider {
    display: none;
  }
  .editor-shell {
    min-height: 480px;
  }
}
</style>
