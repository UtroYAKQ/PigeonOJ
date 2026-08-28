<script setup lang="ts">
/**
 * 写题工作台大组件：左栏题面卡片 + 可拖拽分隔条 + 右栏编辑器与自测控制台。
 * 工具行按钮只抛事件、行为由宿主页面注入——普通做题传 @submit 走正式提交，
 * 验题页传 @submit 走自行验题提交，@self-test 走用户自测（docs/contracts/judge.md）。
 * 分栏比例全局持久化（useSplitPane），窄屏（<900px）自动上下堆叠。
 */
import { nextTick, onMounted, ref, watch } from 'vue'
import { useEventListener } from '@vueuse/core'
import { useI18n } from 'vue-i18n'

import { useSplitPane } from '@/composables/useSplitPane'
import { languageOptions } from '@/constants/languages'
import CodeEditor from '@/components/CodeEditor.vue'
import ProblemMetaBar from '@/components/problem/ProblemMetaBar.vue'
import ProblemStatement from '@/components/problem/ProblemStatement.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { ProblemDetailEx, ProblemLanguage, SelfTestResult } from '@/types'

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
    /** 自测请求进行中 */
    selfTesting?: boolean
    /** 最近一次自测结果（null = 尚未运行） */
    selfTestResult?: SelfTestResult | null
  }>(),
  { showSolution: true, selfTestResult: null },
)

const emit = defineEmits<{
  /** 主提交动作：普通做题 / 自行验题由宿主决定 */
  submit: []
  /** 打开本人该题的提交记录 */
  'show-submissions': []
  /** 用户自测：载荷由宿主从模型组装（code/language/selfTestInput） */
  'self-test': []
}>()

const code = defineModel<string>('code', { required: true })
const language = defineModel<ProblemLanguage>('language', { required: true })
const selfTestInput = defineModel<string>('selfTestInput', { default: '' })

const { t } = useI18n()

// 分栏拖拽与高度实测由 useSplitPane 提供；题目数据就位后重测一次可用高度
const { isDesktop, splitRef, layoutStyle, startResize, resetSplit, updateSplitHeight } =
  useSplitPane()

// 控制台面板：默认收起，展开显示结果；无需持久化（会话级轻量状态）
const collapsed = ref(true)
const activeTab = ref<'result' | 'input'>('result')

// 控制台为编辑器上方浮层，高度可上下拖拽（比例持久化，与分栏 composable 同款交互）
const CONSOLE_H_KEY = 'pigeonoj.problems.consoleHeight.v2'
const CONSOLE_H_DEFAULT = 440
function loadConsoleHeight(): number {
  const raw = Number(localStorage.getItem(CONSOLE_H_KEY))
  return Number.isFinite(raw) && raw >= 120 && raw <= 720 ? raw : CONSOLE_H_DEFAULT
}
const consoleHeight = ref(loadConsoleHeight())
const editorShellRef = ref<HTMLElement>()
let resizingConsole = false

/** 顶缘拖拽带按下：进入高度拖拽（收起态下拖拽自动展开，变化即时可见） */
function startConsoleResize(event: PointerEvent) {
  event.preventDefault()
  resizingConsole = true
  collapsed.value = false
  // 仅禁止文本选中，光标保持不变（用户要求拖拽无光标反馈）
  document.body.classList.add('is-console-resizing')
}

function onConsolePointerMove(event: PointerEvent) {
  if (!resizingConsole || !editorShellRef.value) return
  const rect = editorShellRef.value.getBoundingClientRect()
  const height = Math.round(rect.bottom - event.clientY)
  // 下限保证可读；上限给编辑器留最小操作空间
  consoleHeight.value = Math.min(Math.max(140, height), Math.max(200, Math.floor(rect.height) - 60))
}

function endConsoleResize() {
  if (!resizingConsole) return
  resizingConsole = false
  document.body.classList.remove('is-console-resizing')
  localStorage.setItem(CONSOLE_H_KEY, String(consoleHeight.value))
}

useEventListener(window, 'pointermove', onConsolePointerMove)
useEventListener(window, 'pointerup', endConsoleResize)

const canSelfTest = () => Boolean(code.value.trim()) && !props.selfTesting

function switchTab(tab: 'result' | 'input') {
  // 点击当前已展开的分页再次收起（自测输入/结果都可做展开/收起开关）
  if (activeTab.value === tab && !collapsed.value) {
    collapsed.value = true
    return
  }
  activeTab.value = tab
  collapsed.value = false
}

function onSelfTest() {
  if (!canSelfTest()) return
  activeTab.value = 'result'
  collapsed.value = false
  emit('self-test')
}

function timeText(ms: number | null): string {
  return ms == null ? '-' : `${ms} ms`
}

function memoryText(kb: number | null): string {
  return kb == null ? '-' : `${kb} KB`
}

onMounted(updateSplitHeight)
watch(
  () => props.problem,
  () => nextTick(updateSplitHeight),
)
watch(
  () => props.selfTestResult,
  (value) => {
    if (value) {
      activeTab.value = 'result'
      collapsed.value = false
    }
  },
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

    <!-- 右栏：编辑器工作台 + 自测控制台浮层 -->
    <section class="problem-workbench__editor">
      <div ref="editorShellRef" class="editor-shell">
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
          </div>
        </div>
        <div class="editor-wrap">
          <CodeEditor v-model="code" :language="language" />
        </div>

        <!-- 自测控制台：覆盖在编辑器之上的浮层，顶缘可拖拽调整高度 -->
        <div
          class="console"
          :class="{ 'console--collapsed': collapsed }"
          :style="collapsed ? undefined : { height: `${consoleHeight}px` }"
        >
          <!-- 顶缘拖拽带：小线 + 面板边缘作为滑动判定区（中间切换钮浮于其上） -->
          <div
            class="console__resize"
            role="separator"
            aria-orientation="horizontal"
            :aria-label="t('problems.detail.selfTestResizeHint')"
            @pointerdown="startConsoleResize"
          />
          <button
            type="button"
            class="console__toggle"
            :aria-label="collapsed ? t('problems.detail.selfTestExpand') : t('problems.detail.selfTestCollapse')"
            @click="collapsed = !collapsed"
          >
            <svg viewBox="0 0 16 16" width="10" height="10" aria-hidden="true">
              <path
                d="M3 10l5-5 5 5"
                fill="none"
                stroke="currentColor"
                stroke-width="1.6"
                stroke-linecap="round"
                stroke-linejoin="round"
                :class="{ flipped: !collapsed }"
              />
            </svg>
          </button>
          <div class="console__controls">
            <div class="console__tabs" role="tablist">
              <button
                type="button"
                role="tab"
                class="console__tab"
                :class="{ active: activeTab === 'result' }"
                :aria-selected="activeTab === 'result'"
                @click="switchTab('result')"
              >
                {{ t('problems.detail.selfTestResultTab') }}
              </button>
              <button
                type="button"
                role="tab"
                class="console__tab"
                :class="{ active: activeTab === 'input' }"
                :aria-selected="activeTab === 'input'"
                @click="switchTab('input')"
              >
                {{ t('problems.detail.selfTestInputTab') }}
              </button>
            </div>
            <n-button
              size="small"
              secondary
              type="primary"
              :loading="selfTesting"
              :disabled="!canSelfTest()"
              class="console__run"
              @click="onSelfTest"
            >
              {{ t('problems.detail.selfTestRun') }}
            </n-button>
            <div class="console__spacer" />
            <n-button
              type="primary"
              :loading="submitting"
              :disabled="submitDisabled"
              @click="emit('submit')"
              >{{ t('problems.detail.submit') }}</n-button
            >
          </div>
          <div v-show="!collapsed" class="console__body">
            <template v-if="activeTab === 'input'">
              <n-input
                v-model:value="selfTestInput"
                type="textarea"
                class="console__stdin"
                :placeholder="t('problems.detail.selfTestInputPlaceholder')"
                :autosize="false"
              />
            </template>
            <template v-else>
              <div v-if="selfTesting" class="console__hint">{{ t('problems.detail.selfTestRunning') }}</div>
              <div v-else-if="!selfTestResult" class="console__hint">
                {{ t('problems.detail.selfTestEmptyHint') }}
              </div>
              <div v-else class="console__result">
                <div class="console__meta">
                  <StatusTag :status="selfTestResult.status" />
                  <span class="console__stat">{{ t('problems.submission.time') }}：{{ timeText(selfTestResult.time_used_ms) }}</span>
                  <span class="console__stat">{{ t('problems.submission.memory') }}：{{ memoryText(selfTestResult.memory_used_kb) }}</span>
                </div>
                <pre v-if="selfTestResult.error_message" class="console__stderr">{{
                  selfTestResult.error_message
                }}</pre>
                <pre class="console__stdout">{{ selfTestResult.output || t('problems.detail.noOutput') }}</pre>
              </div>
            </template>
          </div>
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
.editor-shell {
  position: relative;
}

/* 自测控制台：覆盖在编辑器之上的底部浮层，顶缘（小线 + 边缘）可拖拽调高 */
.console {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  /* 高于 Monaco 内部滚动条浮层（z-index:11），避免编辑器右侧滚动条压在自测弹窗上 */
  z-index: 20;
  border-top: 1px solid var(--app-border);
  background: var(--app-card-bg);
  box-shadow: 0 -6px 20px rgb(0 0 0 / 0.08);
}
.console--collapsed {
  height: auto !important;
}
.console__resize {
  position: absolute;
  top: -8px;
  left: 0;
  right: 0;
  height: 14px;
  cursor: default;
  touch-action: none;
  z-index: 3;
}
/* 把手凹口：与面板轮廓融为一体的圆角顶部标签（同底色、边框延续），
   点击切换展开/收起；凹口两侧的顶缘为拖拽区。无悬浮线、无光标/提示变化 */
.console__toggle {
  position: absolute;
  top: -13px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 14px;
  border: 1px solid var(--app-border);
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  background: var(--app-card-bg);
  color: var(--app-text-muted);
  cursor: pointer;
  z-index: 4;
}
.console__toggle svg {
  transition: transform 0.15s ease;
}
.console__toggle svg.flipped {
  transform: rotate(180deg);
}
.console__controls {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
}
.console__tabs {
  display: flex;
  gap: 4px;
}
.console__tab {
  border: none;
  background: transparent;
  padding: 4px 10px;
  border-radius: var(--app-radius-sm, 4px);
  font-size: 13px;
  color: var(--app-text-secondary);
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}
.console__tab.active {
  background: color-mix(in srgb, var(--app-primary, #18a058) 12%, transparent);
  color: var(--app-primary, #18a058);
}
.console__spacer {
  flex: 1;
}
.console__body {
  height: calc(100% - 45px);
  padding: 0 10px 10px;
}
.console__stdin {
  height: 100%;
}
.console__stdin :deep(textarea) {
  height: 100%;
  resize: none;
}
.console__hint {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: var(--app-text-muted);
}
.console__result {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}
.console__meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.console__stat {
  font-size: 12px;
  color: var(--app-text-secondary);
}
.console__stderr,
.console__stdout {
  flex: 1;
  margin: 0;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12.5px;
  line-height: 1.55;
  border-radius: var(--app-radius-sm, 4px);
  padding: 8px 10px;
  min-height: 0;
}
.console__stderr {
  flex: 0 1 auto;
  max-height: 45%;
  color: var(--app-error);
  background: color-mix(in srgb, var(--app-error) 8%, transparent);
}
.console__stdout {
  background: var(--app-surface-muted);
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
