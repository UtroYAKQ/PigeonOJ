<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useEventListener, useResizeObserver } from '@vueuse/core'
import { BookOpen, ChevronDown, History, Loader2 } from '@lucide/vue'

import CodeEditor from '@/components/common/CodeEditor.vue'
import SplitPane from '@/components/common/SplitPane.vue'
import LanguageSelect from '@/components/common/LanguageSelect.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import ProblemMetaBar from '@/components/problem/ProblemMetaBar.vue'
import ProblemStatement from '@/components/problem/ProblemStatement.vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

import type { ProblemDetail, ProblemLanguage, SelfTestResult } from '@/types'

const props = withDefaults(
  defineProps<{
    problem: ProblemDetail
    submitting?: boolean
    submitDisabled?: boolean
    showSolution?: boolean
    hidePublishedStatus?: boolean
    selfTesting?: boolean
    selfTestResult?: SelfTestResult | null
    solutionsHref?: string
  }>(),
  { showSolution: true, selfTestResult: null },
)

const emit = defineEmits<{
  submit: []
  'show-submissions': []
  'self-test': []
}>()

const code = defineModel<string>('code', { required: true })
const language = defineModel<ProblemLanguage>('language', { required: true })
const selfTestInput = defineModel<string>('self-test-input', { default: '' })

const { t } = useI18n()
const router = useRouter()

/**
 * 自测控制台常驻底部：常态只露控制条（自测 / 提交按钮都在这一行），
 * 拖动上方分隔条可自由调整高度，双击复位。高度按 px 持久化，
 * 下限保证可读，上限给编辑器留出最小空间。
 */
// 对齐旧 UI：默认 440px、下限 140px；沿用旧键以继承老用户调好的高度
const CONSOLE_HEIGHT_KEY = 'pigeonoj.problems.consoleHeight.v2'
const LEGACY_CONSOLE_HEIGHT_KEY = 'pigeonoj.problems.consoleHeight'
const CONSOLE_HEIGHT_DEFAULT = 440
const CONSOLE_HEIGHT_MIN = 140
const EDITOR_MIN_HEIGHT = 220

function loadConsoleHeight(): number {
  for (const key of [CONSOLE_HEIGHT_KEY, LEGACY_CONSOLE_HEIGHT_KEY]) {
    const raw = Number(localStorage.getItem(key))
    if (Number.isFinite(raw) && raw >= CONSOLE_HEIGHT_MIN && raw <= 720) return raw
  }
  return CONSOLE_HEIGHT_DEFAULT
}

const consoleCollapsed = ref(true)
const consoleHeight = ref(loadConsoleHeight())
const activeTab = ref<'result' | 'input'>('result')
const rightRef = ref<HTMLElement>()
const toolbarRef = ref<HTMLElement>()
const editorRef = ref<HTMLElement>()
const consoleRef = ref<HTMLElement>()

let resizing = false
let tracking = false
let dragStarted = false

let startY = 0
let startHeight = 0

let resizeFrame: number | undefined
let pendingY = 0

const consoleStyle = computed(() =>
  consoleCollapsed.value ? undefined : { height: `${consoleHeight.value}px` },
)

function clampConsoleHeight(value: number): number {
  const available = rightRef.value?.clientHeight ?? 0
  // 按工具栏实际高度预留空间：换行变高时也不会让编辑器盖住控制台
  const editorMin =
    (editorRef.value && parseFloat(getComputedStyle(editorRef.value).minHeight)) ||
    EDITOR_MIN_HEIGHT
  const reserved = (toolbarRef.value?.offsetHeight ?? 0) + editorMin
  const max = Math.max(CONSOLE_HEIGHT_MIN, Math.floor(available - reserved))
  return Math.min(max, Math.max(CONSOLE_HEIGHT_MIN, value))
}

function persistConsoleHeight(): void {
  try {
    localStorage.setItem(CONSOLE_HEIGHT_KEY, String(consoleHeight.value))
  } catch {
    /* 持久化不可用时仅保留当前会话高度 */
  }
}

function applyResize(): void {
  resizeFrame = undefined
  if (!resizing) return
  consoleHeight.value = clampConsoleHeight(startHeight + startY - pendingY)
  consoleCollapsed.value = false
}

function toggleConsole(): void {
  if (consoleCollapsed.value) {
    consoleHeight.value = clampConsoleHeight(consoleHeight.value)
    consoleCollapsed.value = false
  } else {
    consoleCollapsed.value = true
  }
}

/** 把手单击开合：鼠标/触控的单击在 pointerup 里处理，detail=0 才是键盘触发 */
function onHandleClick(event: MouseEvent): void {
  if (event.detail !== 0) return
  toggleConsole()
}

function onHandlePointerDown(event: PointerEvent): void {
  if (event.button !== 0) return
  event.preventDefault()
  tracking = true
  dragStarted = false
  startY = event.clientY
  // 从收起态起拖时以控制条实际高度为基准，展开过程跟手不跳变
  startHeight = consoleRef.value?.getBoundingClientRect().height ?? consoleHeight.value
}

function beginDrag(): void {
  dragStarted = true
  resizing = true
  if (consoleCollapsed.value) {
    consoleCollapsed.value = false
    startHeight = CONSOLE_HEIGHT_MIN
    startY = pendingY
  }
  document.body.classList.add('is-console-resizing')
}

function onResizeMove(event: PointerEvent): void {
  if (!tracking) return
  pendingY = event.clientY
  if (!dragStarted) {
    // 位移超过 3px 才进入拖拽，轻点仍视为开合
    if (Math.abs(pendingY - startY) < 3) return
    beginDrag()
  }
  if (resizeFrame !== undefined) return
  resizeFrame = requestAnimationFrame(applyResize)
}

function onResizeEnd(): void {
  if (!tracking && !resizing) return
  const wasDrag = dragStarted
  tracking = false
  dragStarted = false
  if (resizeFrame !== undefined) {
    cancelAnimationFrame(resizeFrame)
    resizeFrame = undefined
  }
  document.body.classList.remove('is-console-resizing')

  if (!wasDrag) {
    toggleConsole()
    return
  }

  resizing = false
  // 旧 UI 手感：展开态拖得太小视为取消，还原拖前高度并收起
  if (consoleHeight.value <= CONSOLE_HEIGHT_MIN && startHeight > CONSOLE_HEIGHT_MIN) {
    consoleCollapsed.value = true
    consoleHeight.value = startHeight
  } else {
    consoleHeight.value = clampConsoleHeight(consoleHeight.value)
  }
  persistConsoleHeight()
}

function onTabClick(value: 'result' | 'input'): void {
  if (!consoleCollapsed.value && activeTab.value === value) {
    consoleCollapsed.value = true
    return
  }
  activeTab.value = value
  consoleCollapsed.value = false
}


function onResizeKeydown(event: KeyboardEvent): void {
  const step = event.shiftKey ? 64 : 24
  if (event.key === 'ArrowUp') consoleHeight.value = clampConsoleHeight(consoleHeight.value + step)
  else if (event.key === 'ArrowDown')
    consoleHeight.value = clampConsoleHeight(consoleHeight.value - step)
  else if (event.key === 'Home') consoleHeight.value = clampConsoleHeight(CONSOLE_HEIGHT_DEFAULT)
  else return
  event.preventDefault()
  consoleCollapsed.value = false
  persistConsoleHeight()
}

useEventListener(window, 'pointermove', onResizeMove)
useEventListener(window, 'pointerup', onResizeEnd)
useEventListener(window, 'pointercancel', onResizeEnd)
useEventListener(window, 'blur', onResizeEnd)
// 容器尺寸变化（窗口缩放 / 左右分栏拖动导致工具栏换行）后重新约束高度
useResizeObserver(rightRef, () => {
  if (!resizing) consoleHeight.value = clampConsoleHeight(consoleHeight.value)
})
onBeforeUnmount(() => {
  if (resizeFrame !== undefined) cancelAnimationFrame(resizeFrame)
  document.body.classList.remove('is-console-resizing')
})

watch(
  () => props.selfTestResult,
  (value) => {
    if (!value) return
    activeTab.value = 'result'
    consoleCollapsed.value = false
  },
)

function runSelfTest(): void {
  if (!code.value.trim() || props.selfTesting) return
  activeTab.value = 'result'
  consoleHeight.value = clampConsoleHeight(consoleHeight.value)
  consoleCollapsed.value = false
  emit('self-test')
}
</script>

<template>
  <SplitPane storage-key="pigeonoj.problems.split">
    <template #left>
      <Card class="min-h-full overflow-hidden">
        <div class="border-b border-border px-4 py-3.5">
          <ProblemMetaBar
            :problem="problem"
            show-title
            :hide-published-status="hidePublishedStatus"
          />
        </div>
        <div class="px-4 py-4">
          <ProblemStatement :problem="problem" :show-solution="showSolution" />
        </div>
      </Card>
    </template>

    <template #right>
      <section ref="rightRef" class="code-surface flex h-full min-h-[360px] flex-col lg:min-h-[420px]">
        <div ref="toolbarRef" class="flex shrink-0 flex-wrap items-center gap-2 pb-2">
          <LanguageSelect v-model="language" />
          <div class="ml-auto flex items-center gap-2">
            <Button variant="outline" size="sm" @click="emit('show-submissions')">
              <History class="size-4" />
              {{ t('problems.detail.mySubmissions') }}
            </Button>
            <Button
              v-if="solutionsHref"
              variant="outline"
              size="sm"
              @click="router.push(solutionsHref)"
            >
              <BookOpen class="size-4" />
              {{ t('problems.solutions.title') }}
            </Button>
          </div>
        </div>

        <div ref="editorRef" class="min-h-[220px] flex-1 lg:min-h-[260px]">
          <CodeEditor v-model="code" :language="language" />
        </div>

        <div
          ref="consoleRef"
          class="relative z-10 flex shrink-0 flex-col overflow-visible rounded-xl border border-border bg-card"
          :style="consoleStyle"
        >
          <button
            type="button"
            data-slot="console-handle"
            class="absolute -top-3.5 left-1/2 z-20 flex h-3.5 w-16 -translate-x-1/2 cursor-pointer touch-none items-center justify-center rounded-t-lg border border-b-0 border-border bg-card text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
            :aria-label="
              consoleCollapsed
                ? t('problems.detail.selfTestExpand')
                : t('problems.detail.selfTestCollapse')
            "
            :aria-expanded="!consoleCollapsed"
            :title="t('problems.detail.selfTestResizeHint')"
            @click="onHandleClick"
            @pointerdown="onHandlePointerDown"
            @keydown="onResizeKeydown"
          >
            <ChevronDown
              class="size-3 transition-transform"
              :class="{ 'rotate-180': consoleCollapsed }"
            />
          </button>
          <div class="flex min-h-0 flex-1 flex-col">
            <div class="flex shrink-0 flex-wrap items-center gap-2 border-b border-border px-2.5 py-1.5">
              <div role="tablist" class="flex items-center gap-1">
                <Button
                  :variant="activeTab === 'result' ? 'secondary' : 'ghost'"
                  size="xs"
                  role="tab"
                  :aria-selected="activeTab === 'result'"
                  :class="activeTab === 'result' ? 'text-foreground' : 'text-muted-foreground'"
                  @click="onTabClick('result')"
                >
                  {{ t('problems.detail.selfTestResultTab') }}
                </Button>
                <Button
                  :variant="activeTab === 'input' ? 'secondary' : 'ghost'"
                  size="xs"
                  role="tab"
                  :aria-selected="activeTab === 'input'"
                  :class="activeTab === 'input' ? 'text-foreground' : 'text-muted-foreground'"
                  @click="onTabClick('input')"
                >
                  {{ t('problems.detail.selfTestInputTab') }}
                </Button>
              </div>
              <span class="h-4 w-px shrink-0 bg-border" aria-hidden="true" />
              <Button
                variant="outline"
                size="sm"
                :disabled="!code.trim() || selfTesting"
                @click="runSelfTest"
              >
                <Loader2 v-if="selfTesting" class="size-4 animate-spin" />
                {{ t('problems.detail.selfTestRun') }}
              </Button>
              <div class="flex-1" />
              <Button size="sm" :disabled="submitDisabled || submitting" @click="emit('submit')">
                <Loader2 v-if="submitting" class="size-4 animate-spin" />
                {{ t('problems.detail.submit') }}
              </Button>
            </div>

            <div
              v-show="!consoleCollapsed && activeTab === 'result'"
              class="min-h-0 flex-1 overflow-auto p-3"
            >
              <div
                v-if="selfTesting"
                class="grid h-full place-items-center text-[13px] text-muted-foreground"
              >
                {{ t('problems.detail.selfTestRunning') }}
              </div>
              <div
                v-else-if="!selfTestResult"
                class="grid h-full place-items-center text-[13px] text-muted-foreground"
              >
                {{ t('problems.detail.selfTestEmptyHint') }}
              </div>
              <div v-else class="flex h-full min-h-0 flex-col gap-2">
                <div class="flex flex-wrap items-center gap-3">
                  <StatusTag :status="selfTestResult.status" />
                  <span class="text-[12px] text-muted-foreground tabular-nums">
                    {{ t('problems.submission.time') }}：{{
                      selfTestResult.time_used_ms == null
                        ? '-'
                        : `${selfTestResult.time_used_ms} ms`
                    }}
                  </span>
                  <span class="text-[12px] text-muted-foreground tabular-nums">
                    {{ t('problems.submission.memory') }}：{{
                      selfTestResult.memory_used_kb == null
                        ? '-'
                        : `${selfTestResult.memory_used_kb} KB`
                    }}
                  </span>
                </div>
                <pre
                  class="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border px-3 py-2 font-mono text-[12.5px] leading-5"
                  :class="{
                    'text-destructive': selfTestResult.error_message,
                    'text-muted-foreground':
                      !selfTestResult.error_message && !selfTestResult.output,
                  }"
                  >{{
                    selfTestResult.error_message ||
                    selfTestResult.output ||
                    t('problems.detail.noOutput')
                  }}</pre>
              </div>
            </div>

            <div v-show="!consoleCollapsed && activeTab === 'input'" class="min-h-0 flex-1 p-3">
              <textarea
                v-model="selfTestInput"
                :placeholder="t('problems.detail.selfTestInputPlaceholder')"
                class="h-full w-full resize-none rounded-lg border border-border bg-transparent px-3 py-2 font-mono text-[12.5px] leading-5 outline-none placeholder:text-muted-foreground focus-visible:border-ring"
              />
            </div>
          </div>
        </div>
      </section>
    </template>
  </SplitPane>
</template>
