<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { KeyRound, Loader2 } from '@lucide/vue'

import { getOrgProblem } from '@/api/orgs'
import {
  applyTestCases,
  getProblem,
  initVerification,
  publishProblem,
  submitVerifyCode,
} from '@/api/problems'
import { getTeamProblem } from '@/api/teams'
import ToneBadge from '@/components/common/ToneBadge.vue'
import MySubmissionsDialog from '@/components/problem/MySubmissionsDialog.vue'
import ProblemWorkbench from '@/components/problem/ProblemWorkbench.vue'
import { Button } from '@/components/ui/button'
import { TooltipHint } from '@/components/ui/tooltip'
import { useSelfTest } from '@/composables/useSelfTest'
import { confirmDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { ProblemDetail, ProblemLanguage } from '@/types'
import VerifyInviteDialog from '@/views/problems/components/VerifyInviteDialog.vue'
import WizardSteps from '@/views/problems/components/WizardSteps.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const problemId = String(route.params.id ?? route.params.problemId)
/** 团队 / 组织上下文：跳转与评测结果均留在本上下文路由 */
const teamId = route.params.teamId ? String(route.params.teamId) : null
const isTeam = teamId !== null
const orgId = route.params.orgId ? String(route.params.orgId) : null
const isOrg = orgId !== null
/** 完整详情（含验题状态），驱动门禁与状态标签 */
const detail = ref<ProblemDetail | null>(null)

// ---- 工作台状态（v-model 双向绑定给 ProblemWorkbench）----
const code = ref('')
const language = ref<ProblemLanguage>('cpp17')

// ---- 用户自测（控制台面板；验题人调试代码用，与做题页同款）----
const {
  selfTestInput,
  selfTesting,
  selfTestResult,
  runSelfTest: doSelfTest,
} = useSelfTest(() => problemId)

// ---- 验题状态标签与发布门禁（以后端 needs_reverification 为准）----
type VerifyState = 'verified' | 'stale' | 'unverified'

const state = computed<VerifyState>(() => {
  if (!detail.value?.is_verified) return 'unverified'
  return detail.value.needs_reverification ? 'stale' : 'verified'
})

/** 卡片头只放短标签（与「我的题目」列表口径一致）；通过时间 / 变更原因收进悬停提示 */
const stateLabel = computed(() => {
  if (state.value === 'verified') return t('problems.manage.verifiedTag')
  return state.value === 'stale'
    ? t('problems.manage.reverifyTag')
    : t('problems.manage.unverifiedTag')
})
const stateHint = computed(() => {
  if (state.value === 'verified') {
    return detail.value?.verified_at
      ? t('problems.manage.verifiedAt', { time: formatDateTime(detail.value.verified_at) })
      : ''
  }
  return state.value === 'stale' ? t('problems.manage.reverifyRequired') : ''
})

const publishBlocked = computed(
  () => !detail.value?.is_verified || Boolean(detail.value?.needs_reverification),
)

/** 上下文内题目基路径（我的提交弹窗按 基路径/submissions/:id 跳转） */
const problemBase = computed(() =>
  isOrg
    ? `/orgs/${orgId}/problems/${problemId}`
    : isTeam
      ? `/teams/${teamId}/problems/${problemId}`
      : `/problems/${problemId}`,
)
const submissionsBase = computed(() => `${problemBase.value}/submissions`)

// ---- 自行验题提交（工作台主按钮触发）----
const submitting = ref(false)

/** 确保存在进行中的验题记录（已有 pending 时忽略 3003 直接尝试提交） */
async function ensureSelfVerification(): Promise<void> {
  try {
    await initVerification(problemId, {})
  } catch {
    /* 已有进行中的验题（3003）等场景：交由提交接口给出最终错误 */
  }
}

async function onSubmit(): Promise<void> {
  if (!code.value.trim() || submitting.value) return
  submitting.value = true
  try {
    await ensureSelfVerification()
    const result = await submitVerifyCode(problemId, {
      code: code.value,
      language: language.value,
    })
    message.success(t('problems.verify.submitted'))
    void router.push(`${submissionsBase.value}/${result.submission_id}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    submitting.value = false
  }
}

function runSelfTest(): void {
  void doSelfTest({ language: language.value, code: code.value })
}

// ---- 我的提交弹窗（工作台「我的提交」按钮触发时才请求 + 分页）----
const subsOpen = ref(false)

// ---- 邀请验题 / 发布 / 生效 ----
const inviteOpen = ref(false)
const publishing = ref(false)
const applying = ref(false)

async function onPublish(): Promise<void> {
  const ok = await confirmDialog({
    title: t('problems.detail.publish'),
    content: t('problems.manage.publishConfirm'),
    positiveText: t('problems.detail.publish'),
    negativeText: t('action.cancel'),
  })
  if (!ok) return
  publishing.value = true
  try {
    await publishProblem(problemId)
    message.success(t('problems.detail.publishSuccess'))
    // 发布成功后回到管理工作台（前台详情页不承载管理动线）
    void router.push(isOrg ? `/orgs/${orgId}` : '/admin/problems')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    publishing.value = false
  }
}

/** 显式生效：把已通过验题的暂存集晋升为生效集（验题与晋升解耦） */
async function onApply(): Promise<void> {
  applying.value = true
  try {
    await applyTestCases(problemId)
    message.success(t('problems.manage.applySuccess'))
    await loadExisting()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    applying.value = false
  }
}

async function loadExisting(): Promise<void> {
  loading.value = true
  try {
    const loaded: ProblemDetail = await (isOrg
      ? getOrgProblem(orgId!, problemId)
      : isTeam
        ? getTeamProblem(teamId!, problemId)
        : getProblem(problemId))
    if (!loaded.can_manage) throw new Error(t('problems.create.noPermission'))
    detail.value = loaded
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
    void router.push(isOrg ? `/orgs/${orgId}` : isTeam ? `/teams/${teamId}` : '/admin/problems')
  } finally {
    loading.value = false
  }
}

function goPrev(): void {
  void router.push(
    isOrg
      ? `/orgs/${orgId}/problems/${problemId}/edit/cases`
      : isTeam
        ? `/teams/${teamId}/problems/${problemId}/edit/cases`
        : `/admin/problems/${problemId}/edit/cases`,
  )
}

function cancelEdit(): void {
  // 未发布离开：草稿保留，可随时从管理工作台继续
  void router.push(isOrg ? `/orgs/${orgId}` : isTeam ? `/teams/${teamId}` : '/admin/problems')
}

onMounted(() => void loadExisting())
</script>

<template>
  <div class="mx-auto w-full max-w-[1200px] px-4 pb-12 pt-4 sm:px-6">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <h1 class="text-xl font-semibold leading-tight tracking-tight">
            {{ t('problems.wizard.verifyPublish') }}
          </h1>
          <!-- 验题状态短标签：详情（通过时间 / 变更原因）收进悬停提示 -->
          <TooltipHint :text="stateHint">
            <ToneBadge
              v-if="state !== 'unverified'"
              :tone="state === 'verified' ? 'success' : 'warning'"
              :label="stateLabel"
            />
            <ToneBadge v-else tone="default" :label="stateLabel" />
          </TooltipHint>
        </div>
        <div class="mt-2">
          <WizardSteps :current="3" />
        </div>
      </div>
    </header>

    <div class="my-5 h-px bg-border" role="separator" />

    <div v-if="loading" class="grid h-[320px] place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <!-- 双栏工作台：左题面 + 右编辑器；无卡片外壳 -->
    <div v-else-if="detail" class="min-[900px]:h-[calc(100dvh-15rem)] min-[900px]:min-h-[520px]">
      <ProblemWorkbench
        v-model:code="code"
        v-model:language="language"
        v-model:self-test-input="selfTestInput"
        :problem="detail"
        :submitting="submitting"
        :submit-disabled="!code.trim()"
        :self-testing="selfTesting"
        :self-test-result="selfTestResult"
        :show-solution="false"
        @show-submissions="subsOpen = true"
        @submit="onSubmit"
        @self-test="runSelfTest"
      />
    </div>

    <div v-else class="grid h-[320px] place-items-center text-[13px] text-muted-foreground">
      {{ t('problems.detail.loadFailed') }}
    </div>

    <div class="mt-8 flex flex-wrap justify-start gap-2">
      <!-- 已验证的暂存测试点：显式生效入口（点了保存才晋升，验题与晋升解耦） -->
      <Button v-if="detail?.case_status === 'verified'" :disabled="applying" @click="onApply">
        <Loader2 v-if="applying" class="size-4 animate-spin" />
        {{ t('problems.manage.applyStaged') }}
      </Button>

      <!-- 已发布题目无发布动作（重新发布场景走重新验题 → 门禁自动恢复按钮） -->
      <TooltipHint
        v-if="detail?.status !== 'published'"
        :text="t('problems.manage.publishNeedVerified')"
        :disabled="!publishBlocked"
      >
        <!-- span 作为触发器：禁用态按钮不派发指针事件，直接包 Button 会让提示失效 -->
        <span class="inline-flex">
          <Button :disabled="publishBlocked || loading || publishing" @click="onPublish">
            <Loader2 v-if="publishing" class="size-4 animate-spin" />
            {{ t('problems.detail.publish') }}
          </Button>
        </span>
      </TooltipHint>

      <Button variant="outline" :disabled="loading" @click="goPrev">
        {{ t('problems.wizard.prev') }}
      </Button>
      <Button variant="outline" :disabled="loading" @click="inviteOpen = true">
        <KeyRound class="size-4" />
        {{ t('problems.manage.inviteVerify') }}
      </Button>
      <Button variant="ghost" @click="cancelEdit">{{ t('action.cancel') }}</Button>
    </div>

    <MySubmissionsDialog
      v-model:open="subsOpen"
      :problem-id="problemId"
      :submissions-base="problemBase"
    />

    <VerifyInviteDialog v-model:open="inviteOpen" :problem-id="problemId" />
  </div>
</template>
