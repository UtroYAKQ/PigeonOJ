<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2, LogIn } from '@lucide/vue'

import { createSubmission } from '@/api/judge'
import { resolveVerifyInvite } from '@/api/problems'
import CodeEditor from '@/components/common/CodeEditor.vue'
import InlineNotice from '@/components/common/InlineNotice.vue'
import LanguageSelect from '@/components/common/LanguageSelect.vue'
import MarkdownView from '@/components/common/MarkdownView.vue'
import SplitPane from '@/components/common/SplitPane.vue'
import BrandMark from '@/layout/BrandMark.vue'
import ProblemSamples from '@/components/problem/ProblemSamples.vue'
import { Button } from '@/components/ui/button'
import { confirmDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import type { ProblemLanguage } from '@/types'

interface InviteResolution {
  problem_id: string
  problem_title: string
  expires_at: string | null
  background: string
  description: string
  input_description?: string | null
  output_description?: string | null
  note?: string | null
  tags: string[]
  time_limit_ms: number
  memory_limit_mb: number
  samples: Array<{ name: string; input: string; output: string; explanation?: string }>
}

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()
const appStore = useAppStore()

const resolving = ref(true)
const failed = ref('')
const invite = ref<InviteResolution | null>(null)
const language = ref<ProblemLanguage>('cpp17')
const code = ref('')
const submitting = ref(false)

const token = computed(() => String(route.params.token ?? ''))
const loginRedirect = computed(() => `/verify/${token.value}`)

async function resolve(): Promise<void> {
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

async function submit(): Promise<void> {
  if (!invite.value || !code.value.trim()) return
  const ok = await confirmDialog({
    title: t('problems.verify.submit'),
    content: t('problems.verify.submitConfirm'),
    positiveText: t('problems.verify.submit'),
    negativeText: t('action.cancel'),
  })
  if (!ok) return
  submitting.value = true
  try {
    const result = await createSubmission({
      problem_id: invite.value.problem_id,
      language: language.value,
      code: code.value,
      invite_token: token.value,
    })
    message.success(t('problems.verify.submitted'))
    router.push(`/problems/${invite.value.problem_id}/submissions/${result.submission_id}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="min-h-dvh bg-background p-4 text-foreground md:p-6">
    <header class="mb-4 flex items-center justify-between">
      <router-link to="/" class="flex w-fit items-center gap-2.5 text-[14px] font-semibold">
        <BrandMark size="sm" />
        <span>{{ appStore.siteName }}</span>
      </router-link>
      <span class="text-[12px] text-muted-foreground">{{ t('problems.verify.title') }}</span>
    </header>

    <div v-if="resolving" class="grid h-[60vh] place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="failed" class="grid place-items-center py-16">
      <div
        class="w-full max-w-[520px] rounded-xl border border-border bg-card px-6 py-10 text-center"
      >
        <p class="text-[15px] font-semibold">{{ t('problems.verify.invalid') }}</p>
        <p class="mt-1.5 text-[13px] text-muted-foreground">{{ failed }}</p>
        <Button variant="outline" size="sm" class="mt-5" @click="router.push('/')">
          {{ t('problems.verify.backHome') }}
        </Button>
      </div>
    </div>

    <div v-else-if="invite" class="min-[900px]:h-[calc(100dvh-7rem)]">
      <SplitPane storage-key="pigeonoj.verify.split">
        <template #left>
          <article class="rounded-xl border border-border bg-card">
            <header class="space-y-2 border-b border-border px-5 py-4">
              <p class="text-[12px] font-medium text-brand">{{ t('problems.verify.title') }}</p>
              <h1 class="text-[19px] font-semibold leading-snug">{{ invite.problem_title }}</h1>
              <div
                class="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-muted-foreground"
              >
                <span class="tabular-nums">{{ invite.time_limit_ms }} ms</span>
                <span class="tabular-nums">{{ invite.memory_limit_mb }} MB</span>
                <span v-if="invite.expires_at" class="tabular-nums">
                  {{ t('problems.verify.expiresLabel') }}：{{ formatDateTime(invite.expires_at) }}
                </span>
                <span v-else>{{ t('problems.verify.noExpiry') }}</span>
              </div>
              <div v-if="invite.tags.length" class="flex flex-wrap gap-1.5">
                <span
                  v-for="name in invite.tags"
                  :key="name"
                  class="inline-flex h-5 items-center rounded-md border border-border px-1.5 text-[11.5px] text-muted-foreground"
                >
                  {{ name }}
                </span>
              </div>
            </header>
            <div class="px-5 py-4">
              <template v-if="invite.background">
                <h3 class="mb-2 mt-0 text-[15px] font-semibold">
                  {{ t('problems.detail.background') }}
                </h3>
                <MarkdownView :source="invite.background" />
              </template>
              <h3
                class="mb-2 mt-6 border-t border-border pt-4 text-[15px] font-semibold"
                :class="{ 'mt-0 border-0 pt-0': !invite.background }"
              >
                {{ t('problems.detail.description') }}
              </h3>
              <MarkdownView :source="invite.description" />
              <template v-if="invite.input_description">
                <h3 class="mb-2 mt-6 border-t border-border pt-4 text-[15px] font-semibold">
                  {{ t('problems.detail.inputDescription') }}
                </h3>
                <MarkdownView :source="invite.input_description" />
              </template>
              <template v-if="invite.output_description">
                <h3 class="mb-2 mt-6 border-t border-border pt-4 text-[15px] font-semibold">
                  {{ t('problems.detail.outputDescription') }}
                </h3>
                <MarkdownView :source="invite.output_description" />
              </template>
              <template v-if="invite.samples.length">
                <h3 class="mb-2 mt-6 border-t border-border pt-4 text-[15px] font-semibold">
                  {{ t('problems.detail.samples') }}
                </h3>
                <ProblemSamples :samples="invite.samples" />
              </template>
              <template v-if="invite.note">
                <h3 class="mb-2 mt-6 border-t border-border pt-4 text-[15px] font-semibold">
                  {{ t('problems.detail.note') }}
                </h3>
                <MarkdownView :source="invite.note" />
              </template>
            </div>
          </article>
        </template>

        <template #right>
          <section class="flex h-full min-h-[420px] flex-col gap-2">
            <template v-if="!userStore.isLoggedIn">
              <InlineNotice tone="warning">
                {{ t('problems.verify.loginRequired') }}
              </InlineNotice>
              <Button
                class="w-fit"
                @click="router.push({ path: '/login', query: { redirect: loginRedirect } })"
              >
                <LogIn class="size-4" />
                {{ t('problems.verify.goLogin') }}
              </Button>
            </template>

            <template v-else>
              <div class="flex flex-wrap items-center gap-2">
                <LanguageSelect v-model="language" />
                <div class="flex-1" />
                <Button size="sm" :disabled="!code.trim() || submitting" @click="submit">
                  <Loader2 v-if="submitting" class="size-4 animate-spin" />
                  {{ t('problems.verify.submit') }}
                </Button>
              </div>
              <div class="min-h-[320px] flex-1">
                <CodeEditor v-model="code" :language="language" />
              </div>
            </template>
          </section>
        </template>
      </SplitPane>
    </div>
  </div>
</template>
