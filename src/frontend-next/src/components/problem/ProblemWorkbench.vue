<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useEventListener, useResizeObserver } from '@vueuse/core'
import { BookOpen, ChevronDown, FlaskConical, History, Loader2, Terminal } from '@lucide/vue'

import CodeEditor from '@/components/common/CodeEditor.vue'
import SplitPane from '@/components/common/SplitPane.vue'
import LanguageSelect from '@/components/common/LanguageSelect.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import ProblemMetaBar from '@/components/problem/ProblemMetaBar.vue'
import ProblemStatement from '@/components/problem/ProblemStatement.vue'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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
const CONSOLE_HEIGHT_KEY = 'pigeonoj.problems.consoleHeight'
const CONSOLE_HEIGHT_DEFAULT = 260
// 展开态下限：除标题行外至少留出一屏可读的输出区域，避免文字被裁掉一半
const CONSOLE_HEIGHT_MIN = 180
const EDITOR_MIN_HEIGHT = 160
const RESIZE_HANDLE_HEIGHT = 12

function loadConsoleHeight(): number {
  const raw = Number(localStorage.getItem(CONSOLE_HEIGHT_KEY))
  return Number.isFinite(raw) && raw >= CONSOLE_HEIGHT_MIN && raw <= 720
    ? raw
    : CONSOLE_HEIGHT_DEFAULT
}

const consoleCollapsed = ref(true)
const consoleHeight = ref(loadConsoleHeight())
const activeTab = ref<'result' | 'input'>('result')
const rightRef = ref<HTMLElement>()
const toolbarRef = ref<HTMLElement>()
const editorRef = ref<HTMLElement>()
const consoleRef = ref<HTMLElement>()

let resizing = false
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
  const reserved = (toolbarRef.value?.offsetHeight ?? 0) + editorMin + RESIZE_HANDLE_HEIGHT
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

function onResizeStart(event: PointerEvent): void {
  if (event.button !== 0) return
  event.preventDefault()
  resizing = true
  startY = event.clientY
  // 从收起态起拖时以控制条实际高度为基准，展开过程跟手不跳变
  startHeight = consoleRef.value?.getBoundingClientRect().height ?? consoleHeight.value
  document.body.classList.add('is-console-resizing')
}

function onResizeMove(event: PointerEvent): void {
  if (!resizing) return
  pendingY = event.clientY
  if (resizeFrame !== undefined) return
  resizeFrame = requestAnimationFrame(applyResize)
}

function onResizeEnd(): void {
  if (!resizing) return
  resizing = false
  if (resizeFrame !== undefined) {
    cancelAnimationFrame(resizeFrame)
    resizeFrame = undefined
  }
  document.body.classList.remove('is-console-resizing')
  persistConsoleHeight()
}

function resetConsoleHeight(): void {
  consoleHeight.value = clampConsoleHeight(CONSOLE_HEIGHT_DEFAULT)
  consoleCollapsed.value = false
  persistConsoleHeight()
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
  consoleCollapsed.value = false
  emit('self-test')
}
</script>

<template>
  <SplitPane storage-key="pigeonoj.problems.split">
    <template #left>
      <section class="min-h-full overflow-hidden rounded-xl border border-border bg-card">
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
      </section>
    </template>

    <template #right>
      <section ref="rightRef" class="flex h-full min-h-[420px] flex-col">
        <div ref="toolbarRef" class="flex shrink-0 flex-wrap items-center gap-2 pb-2">
          <LanguageSelect v-model="language" />
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

        <div ref="editorRef" class="min-h-[160px] flex-1">
          <CodeEditor v-model="code" :language="language" />
        </div>

        <div
          class="group flex h-3 shrink-0 cursor-row-resize touch-none items-center justify-center focus-visible:outline-none"
          role="separator"
          aria-orientation="horizontal"
          tabindex="0"
          :aria-label="t('problems.detail.selfTestResizeHint')"
          :title="t('problems.detail.selfTestResizeHint')"
          @pointerdown="onResizeStart"
          @dblclick="resetConsoleHeight"
          @keydown="onResizeKeydown"
        >
          <span
            class="h-1 w-10 rounded-full bg-border transition-colors group-hover:bg-brand group-focus-visible:bg-brand"
          />
        </div>

        <div
          ref="consoleRef"
          class="flex shrink-0 flex-col overflow-hidden rounded-xl border border-border bg-card"
          :style="consoleStyle"
        >
          <Tabs v-model="activeTab" class="flex min-h-0 flex-1 flex-col">
            <div class="flex shrink-0 items-center gap-2 border-b border-border px-3 py-2">
              <Terminal class="size-4 text-muted-foreground" />
              <TabsList class="h-7">
                <TabsTrigger value="result" class="px-2.5 text-[12px]">
                  {{ t('problems.detail.selfTestResultTab') }}
                </TabsTrigger>
                <TabsTrigger value="input" class="px-2.5 text-[12px]">
                  {{ t('problems.detail.selfTestInputTab') }}
                </TabsTrigger>
              </TabsList>
              <div class="flex-1" />
              <Button
                variant="secondary"
                size="sm"
                :disabled="!code.trim() || selfTesting"
                @click="runSelfTest"
              >
                <Loader2 v-if="selfTesting" class="size-4 animate-spin" />
                <FlaskConical v-else class="size-4" />
                {{ t('problems.detail.selfTestRun') }}
              </Button>
              <Button size="sm" :disabled="submitDisabled || submitting" @click="emit('submit')">
                <Loader2 v-if="submitting" class="size-4 animate-spin" />
                {{ t('problems.detail.submit') }}
              </Button>
              <Button
                variant="ghost"
                size="icon-xs"
                :aria-label="
                  consoleCollapsed
                    ? t('problems.detail.selfTestExpand')
                    : t('problems.detail.selfTestCollapse')
                "
                @click="consoleCollapsed = !consoleCollapsed"
              >
                <ChevronDown
                  class="size-4 transition-transform"
                  :class="{ 'rotate-180': consoleCollapsed }"
                />
              </Button>
            </div>

            <TabsContent
              v-show="!consoleCollapsed"
              value="result"
              class="mt-0 min-h-0 flex-1 overflow-auto p-3"
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
                    {{ t('problems.submission.time') }}：{{ selfTestResult.time_used_ms ?? '-' }} ms
                  </span>
                  <span class="text-[12px] text-muted-foreground tabular-nums">
                    {{ t('problems.submission.memory') }}：{{
                      selfTestResult.memory_used_kb ?? '-'
                    }}
                    KB
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
            </TabsContent>

            <TabsContent v-show="!consoleCollapsed" value="input" class="mt-0 min-h-0 flex-1 p-3">
              <textarea
                v-model="selfTestInput"
                :placeholder="t('problems.detail.selfTestInputPlaceholder')"
                class="h-full w-full resize-none rounded-lg border border-border bg-transparent px-3 py-2 font-mono text-[12.5px] leading-5 outline-none placeholder:text-muted-foreground focus-visible:border-ring"
              />
            </TabsContent>
          </Tabs>
        </div>
      </section>
    </template>
  </SplitPane>
</template>
