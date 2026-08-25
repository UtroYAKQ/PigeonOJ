<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NTag } from 'naive-ui'

import { resolveVerifyInvite } from '@/api/problems'
import { createSubmission } from '@/api/judge'
import type { ProblemLanguage } from '@/types'
import { useUserStore } from '@/stores/user'
import { dialog, message } from '@/utils/feedback'
import { useSplitPane } from '@/composables/useSplitPane'
import { languageOptions } from '@/constants/languages'
import CodeEditor from '@/components/CodeEditor.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import ProblemSamples from '@/components/ProblemSamples.vue'
import { formatDateTime } from '@/utils/format'

interface InviteResolution {
  problem_id: string
  problem_title: string
  expires_at: string | null
  description: string
  input_description?: string | null
  output_description?: string | null
  tags: string[]
  time_limit_ms: number
  memory_limit_mb: number
  samples: Array<{ name: string; input: string; output: string }>
}

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

// 与题库详情页同款可拖拽分栏（比例共享持久化；窄屏自动上下堆叠）
const { isDesktop, splitRef, layoutStyle, startResize, resetSplit } = useSplitPane()

const resolving = ref(true)
const failed = ref('')
const invite = ref<InviteResolution | null>(null)
const language = ref<ProblemLanguage>('cpp17')
const code = ref('')
const submitting = ref(false)

const token = computed(() => String(route.params.token ?? ''))
const loginRedirect = computed(() => `/verify/${token.value}`)

async function resolve() {
  resolving.value = true
  failed.value = ''
  try {
    invite.value = await resolveVerifyInvite(token.value)
  } catch (error) {
    failed.value = error instanceof Error ? error.message : t('problems.verify.invalid')
  } finally {
    resolving.value = false
  }
}
onMounted(resolve)

function goLogin() {
  router.push({ path: '/login', query: { redirect: loginRedirect.value } })
}

function submit() {
  if (!invite.value) return
  if (!code.value.trim()) return
  dialog.info({
    title: t('problems.verify.submit'),
    content: t('problems.verify.submitConfirm'),
    positiveText: t('problems.verify.submit'),
    negativeText: t('action.cancel'),
    onPositiveClick: async () => {
      submitting.value = true
      try {
        const res = await createSubmission({
          problem_id: invite.value!.problem_id,
          language: language.value,
          code: code.value,
          invite_token: token.value,
        })
        message.success(t('problems.verify.submitted'))
        router.push(`/problems/${invite.value!.problem_id}/submissions/${res.submission_id}`)
      } catch (error) {
        message.error(error instanceof Error ? error.message : t('common.operationFailed'))
      } finally {
        submitting.value = false
      }
    },
  })
}
</script>

<template>
  <div class="verify-page">
    <header class="verify-brand" @click="router.push('/')">
      <span>🐦</span><strong>PigeonOJ</strong>
    </header>

    <n-spin :show="resolving">
      <!-- 解析失败 -->
      <main v-if="failed" class="verify-pane">
        <n-card :bordered="false" class="verify-card">
          <n-result status="404" :title="t('problems.verify.invalid')" :description="failed">
            <template #footer>
              <n-button @click="router.push('/')">{{ t('problems.verify.backHome') }}</n-button>
            </template>
          </n-result>
        </n-card>
      </main>

      <!-- 左题面 / 右编辑器，可拖拽分栏 -->
      <div
        v-else-if="invite"
        ref="splitRef"
        class="verify-layout"
        :class="{ stacked: !isDesktop }"
        :style="layoutStyle"
      >
        <!-- 左：题面（独立滚动） -->
        <section class="verify-statement">
          <div class="verify-head">
            <p class="verify-eyebrow">{{ t('problems.verify.title') }}</p>
            <h1>{{ invite.problem_title }}</h1>
            <div class="verify-meta">
              <NTag v-for="name in invite.tags" :key="name" size="small" round :bordered="false">
                {{ name }}
              </NTag>
              <span>{{ invite.time_limit_ms }} ms</span>
              <span>{{ invite.memory_limit_mb }} MB</span>
              <span v-if="invite.expires_at">
                {{ t('problems.verify.expiresLabel') }}：{{ formatDateTime(invite.expires_at) }}
              </span>
              <span v-else>{{ t('problems.verify.noExpiry') }}</span>
            </div>
          </div>

          <section class="verify-content">
            <MarkdownView :source="invite.description" />
            <template v-if="invite.input_description">
              <h3 class="verify-subtitle">{{ t('problems.detail.inputDescription') }}</h3>
              <MarkdownView :source="invite.input_description" />
            </template>
            <template v-if="invite.output_description">
              <h3 class="verify-subtitle">{{ t('problems.detail.outputDescription') }}</h3>
              <MarkdownView :source="invite.output_description" />
            </template>

            <template v-if="invite.samples.length">
              <h3 class="verify-subtitle">{{ t('problems.detail.samples') }}</h3>
              <ProblemSamples :samples="invite.samples" />
            </template>
          </section>
        </section>

        <!-- 可拖拽分隔条（双击复位，与题库详情页一致） -->
        <div
          class="verify-divider"
          role="separator"
          aria-orientation="vertical"
          :aria-label="t('problems.detail.resizeHint')"
          :title="t('problems.detail.resizeHint')"
          @pointerdown="startResize"
          @dblclick="resetSplit"
        />

        <!-- 右：提交验题 -->
        <section class="verify-work">
          <template v-if="!userStore.isLoggedIn">
            <n-alert type="warning" class="verify-alert">{{
              t('problems.verify.loginRequired')
            }}</n-alert>
            <n-button type="primary" block size="large" @click="goLogin">{{
              t('problems.verify.goLogin')
            }}</n-button>
          </template>

          <template v-else>
            <div class="verify-submit-head">
              <n-select v-model:value="language" :options="languageOptions" class="verify-lang" />
              <n-button
                type="primary"
                :loading="submitting"
                :disabled="!code.trim()"
                @click="submit"
              >
                {{ t('problems.verify.submit') }}
              </n-button>
            </div>
            <div class="verify-editor">
              <CodeEditor v-model="code" :language="language" />
            </div>
          </template>
        </section>
      </div>
    </n-spin>
  </div>
</template>

<style scoped>
.verify-page {
  min-height: 100dvh;
  padding: 24px;
  background: var(--app-content-bg);
}
.verify-brand {
  display: flex;
  align-items: center;
  gap: 9px;
  width: max-content;
  margin-bottom: 18px;
  color: var(--app-text);
  cursor: pointer;
  font-size: 16px;
}
.verify-brand span {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-card-bg);
}

/* 解析失败态：居中窄卡 */
.verify-pane {
  display: grid;
  place-items: start center;
  padding-top: clamp(20px, 6vh, 56px);
}
.verify-card {
  width: min(860px, 100%);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

/* 三列网格：左题面 + 分隔条 + 右编辑器，与题库详情页同款。
   独立页无 .app-main 滚动容器，高度直接按视口扣除头部与页面内边距 */
.verify-layout {
  display: grid;
  grid-template-columns: minmax(300px, var(--split, 50%)) auto minmax(360px, 1fr);
  align-items: stretch;
  gap: 4px;
  height: calc(100dvh - 130px);
  min-height: 480px;
}

/* 左：题面（独立滚动） */
.verify-statement {
  overflow-y: auto;
  min-width: 0;
  min-height: 0;
  padding-right: 6px;
}
.verify-head h1 {
  margin: 6px 0 10px;
  font-size: 18px;
}
.verify-eyebrow {
  margin: 0;
  color: var(--app-primary);
  font-size: 13px;
  font-weight: 600;
}
.verify-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 16px;
  color: var(--app-text-secondary);
  font-size: 12px;
  margin-bottom: 14px;
}
.verify-content {
  line-height: 1.75;
}
.verify-subtitle {
  margin: 18px 0 8px;
  padding-top: 14px;
  border-top: 1px solid var(--app-border);
  font-size: 15px;
}

/* 可拖拽分隔条：细长手柄，hover / 聚焦变主色 */
.verify-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  margin: 0 -3px;
  cursor: col-resize;
  touch-action: none;
  z-index: 2;
}
.verify-divider::before {
  content: '';
  width: 4px;
  height: 56px;
  border-radius: var(--app-radius-sm, 4px);
  background: var(--app-border);
  transition: background-color 0.15s ease;
}
.verify-divider:hover::before,
.verify-divider:focus-visible::before {
  background: var(--app-primary);
}

/* 右：工具行 + 编辑器 */
.verify-work {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  min-height: 0;
  padding-left: 10px;
}
.verify-alert {
  align-self: flex-start;
}
.verify-submit-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.verify-lang {
  width: 180px;
}
.verify-editor {
  flex: 1;
  min-height: 0;
}

@media (max-width: 899px) {
  .verify-page {
    padding: 16px;
  }
  .verify-layout.stacked {
    display: block;
    height: auto;
    min-height: 0;
  }
  .verify-statement {
    overflow: visible;
    padding-right: 0;
  }
  .verify-divider {
    display: none;
  }
  .verify-work {
    padding-left: 0;
    margin-top: 16px;
  }
  .verify-submit-head {
    flex-direction: column;
    align-items: stretch;
  }
  .verify-lang {
    width: 100%;
  }
  .verify-editor {
    height: 320px;
    flex: none;
  }
}
</style>
