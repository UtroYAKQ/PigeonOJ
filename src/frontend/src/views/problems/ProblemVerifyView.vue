<script setup lang="ts">
/**
 * 出题向导第 3 步「验题与发布」：双栏工作台复用 ProblemWorkbench 大组件，
 * 验题特有动作（状态标签 / 邀请验题 / 使测试点生效 / 发布）集中在向导卡片头，
 * 工作台工具行与做题页保持一致（语言选择 + 我的提交 + 提交代码）。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Key } from '@element-plus/icons-vue'
import type { DataTableColumns } from 'naive-ui'

import {
  applyTestCases,
  getProblem,
  getVerifyInvite,
  initVerification,
  publishProblem,
  submitVerifyCode,
} from '@/api/problems'
import { listSubmissions } from '@/api/judge'
import type { ProblemDetailEx, ProblemLanguage, Submission } from '@/types'
import { dialog, message } from '@/utils/feedback'
import { copyToClipboard } from '@/utils/clipboard'
import { formatDateTime } from '@/utils/format'
import StatusTag from '@/components/StatusTag.vue'
import ProblemWorkbench from '@/components/problem/ProblemWorkbench.vue'
import WizardShell from '@/components/WizardShell.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const problemId = String(route.params.id)
/** 完整详情（含验题状态），驱动门禁与状态标签 */
const detail = ref<ProblemDetailEx | null>(null)

// ---- 工作台状态（v-model 双向绑定给 ProblemWorkbench）----
const code = ref('')
const language = ref<ProblemLanguage>('cpp17')

// ---- 验题状态标签与发布门禁（卡片头展示，以后端 needs_reverification 为准）----
type VerifyState = 'verified' | 'stale' | 'unverified'

const state = computed<VerifyState>(() => {
  if (!detail.value?.is_verified) return 'unverified'
  return detail.value.needs_reverification ? 'stale' : 'verified'
})

const stateTagType = computed(() =>
  state.value === 'verified' ? 'success' : state.value === 'stale' ? 'warning' : 'default',
)
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

// ---- 自行验题提交（工作台主按钮触发）----
const submitting = ref(false)

/** 确保存在进行中的验题记录（已有 pending 时忽略 3003 直接尝试提交） */
async function ensureSelfVerification() {
  try {
    await initVerification(problemId, {})
  } catch {
    /* 已有进行中的验题（3003）等场景：交由提交接口给出最终错误 */
  }
}

async function onSubmit() {
  if (!code.value.trim() || submitting.value) return
  submitting.value = true
  try {
    await ensureSelfVerification()
    const res = await submitVerifyCode(problemId, {
      code: code.value,
      language: language.value,
    })
    message.success(t('problems.verify.submitted'))
    router.push(`/problems/${problemId}/submissions/${res.submission_id}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    submitting.value = false
  }
}

// ---- 我的提交弹窗（工作台「我的提交」按钮触发，与做题页同款）----
const subsVisible = ref(false)
const mySubmissions = ref<Submission[]>([])

function openSubs() {
  subsVisible.value = true
  void loadMySubmissions()
}
async function loadMySubmissions() {
  try {
    const result = await listSubmissions({ problem_id: problemId, page_size: 5 })
    mySubmissions.value = result.items
  } catch {
    mySubmissions.value = []
  }
}

function openSubmission(row: Submission) {
  subsVisible.value = false
  router.push(`/problems/${problemId}/submissions/${row.id}`)
}

const submissionColumns = computed<DataTableColumns<Submission>>(() => [
  {
    title: t('problems.detail.status'),
    key: 'status',
    minWidth: 150,
    render: (row) => h(StatusTag, { status: row.status }),
  },
  {
    title: t('problems.submission.score'),
    key: 'score',
    width: 80,
    render: (row) => row.score ?? '-',
  },
  {
    title: t('problems.submission.time'),
    key: 'time',
    width: 110,
    render: (row) => `${row.time_used_ms ?? '-'} ms`,
  },
  { title: t('problems.detail.language'), key: 'language', width: 120 },
])

// ---- 邀请验题（卡片头入口：先查现有链接定模式再开弹窗，避免内容跳变）----
const generating = ref(false)
const inviteDialog = ref(false)
const inviteLoading = ref(false)
const inviteMode = ref<'generate' | 'view'>('generate')
const expiryHours = ref<24 | 72 | 168>(72)
const invite = ref<{ token: string; expires_at: string | null } | null>(null)

const inviteLink = computed(() =>
  invite.value ? `${window.location.origin}/verify/${invite.value.token}` : '',
)

const expiryOptions = computed(() => [
  { key: '24', label: t('problems.manage.expiry24'), hours: 24 as const },
  { key: '72', label: t('problems.manage.expiry72'), hours: 72 as const },
  { key: '168', label: t('problems.manage.expiry168'), hours: 168 as const },
])

async function openInviteDialog() {
  if (inviteLoading.value) return
  inviteLoading.value = true
  try {
    const existing = await getVerifyInvite(problemId)
    if (existing) {
      invite.value = existing
      inviteMode.value = 'view'
    } else {
      invite.value = null
      inviteMode.value = 'generate'
    }
  } catch {
    /* 查询失败回退到生成模式 */
    invite.value = null
    inviteMode.value = 'generate'
  } finally {
    inviteDialog.value = true
    inviteLoading.value = false
  }
}

async function generateInvite(hours: 24 | 72 | 168) {
  if (generating.value) return
  generating.value = true
  expiryHours.value = hours
  try {
    const res = await initVerification(problemId, {
      invite_expires_hours: hours,
    })
    invite.value = res.invite ?? null
    inviteMode.value = 'view'
    message.success(t('common.success'))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    generating.value = false
  }
}

async function copyLink() {
  if (await copyToClipboard(inviteLink.value)) {
    message.success(t('problems.detail.copied'))
  } else {
    message.error(t('common.operationFailed'))
  }
}

// ---- 发布（卡片头动作；门禁不满足时禁用并以 tooltip 说明）----
const publishing = ref(false)

function onPublish() {
  dialog.warning({
    title: t('problems.detail.publish'),
    content: t('problems.manage.publishConfirm'),
    positiveText: t('problems.detail.publish'),
    negativeText: t('action.cancel'),
    onPositiveClick: async () => {
      publishing.value = true
      try {
        await publishProblem(problemId)
        message.success(t('problems.detail.publishSuccess'))
        // 发布成功后回到管理工作台（前台详情页不承载管理动线）
        router.push('/admin/problems')
      } catch (error) {
        message.error(error instanceof Error ? error.message : t('common.operationFailed'))
      } finally {
        publishing.value = false
      }
    },
  })
}

// ---- 显式生效：把已通过验题的暂存集晋升为生效集（验题与晋升解耦）----
const applying = ref(false)
async function onApply() {
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

async function loadExisting() {
  loading.value = true
  try {
    const loaded: ProblemDetailEx = await getProblem(problemId)
    if (!loaded.can_manage) throw new Error(t('problems.create.noPermission'))
    detail.value = loaded
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
    router.push('/admin/problems')
  } finally {
    loading.value = false
  }
}

function goPrev() {
  router.push(`/admin/problems/${problemId}/edit/cases`)
}
function cancelEdit() {
  // 未发布离开：草稿保留，可随时从管理工作台继续
  router.push('/admin/problems')
}

onMounted(() => void loadExisting())
</script>

<template>
  <div class="page-fill">
    <WizardShell :step="3" :title="t('problems.wizard.verifyPublish')">
      <template #actions>
        <n-button size="small" :disabled="loading" @click="goPrev">
          {{ t('problems.wizard.prev') }}
        </n-button>
        <!-- 验题状态短标签：详情（通过时间 / 变更原因）收进悬停提示，避免长文案挤占按钮行 -->
        <n-tooltip trigger="hover" placement="top" :disabled="!stateHint">
          <template #trigger>
            <n-tag size="small" round :type="stateTagType">{{ stateLabel }}</n-tag>
          </template>
          {{ stateHint }}
        </n-tooltip>
        <!-- 验题特有动作收进向导卡片头，工作台工具行保持与做题页一致 -->
        <n-button secondary size="small" :loading="inviteLoading" @click="openInviteDialog">
          <template #icon><n-icon :component="Key" /></template>
          {{ t('problems.manage.inviteVerify') }}
        </n-button>
        <!-- 已验证的暂存测试点：显式生效入口（点了保存才晋升，验题与晋升解耦） -->
        <n-button
          v-if="detail?.case_status === 'verified'"
          type="primary"
          size="small"
          :loading="applying"
          @click="onApply"
        >
          {{ t('problems.manage.applyStaged') }}
        </n-button>
        <!-- 已发布题目无发布动作（重新发布场景走重新验题 → 门禁自动恢复按钮） -->
        <n-tooltip v-if="detail?.status !== 'published'" trigger="hover" placement="top" :disabled="!publishBlocked">
          <template #trigger>
            <n-button
              type="primary"
              size="small"
              :loading="publishing"
              :disabled="publishBlocked || loading"
              @click="onPublish"
            >
              {{ t('problems.detail.publish') }}
            </n-button>
          </template>
          {{ t('problems.manage.publishNeedVerified') }}
        </n-tooltip>
        <n-button size="small" quaternary @click="cancelEdit">{{ t('action.cancel') }}</n-button>
      </template>

      <!-- 双栏工作台大组件：左题面 + 右编辑器；高度实测在组件内部完成 -->
      <n-spin :show="loading">
        <ProblemWorkbench
          v-if="detail"
          v-model:code="code"
          v-model:language="language"
          :problem="detail"
          :submitting="submitting"
          :submit-disabled="!code.trim()"
          :show-solution="false"
          @show-submissions="openSubs"
          @submit="onSubmit"
        />
      </n-spin>
    </WizardShell>

    <!-- 我的提交弹窗（本人该题最近提交，点击行跳评测结果页） -->
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

    <!-- 邀请验题弹窗 -->
    <n-modal
      v-model:show="inviteDialog"
      preset="card"
      :title="t('problems.manage.inviteDialogTitle')"
      style="max-width: 460px"
    >
      <!-- 已存在有效链接：直接展示，可复制或重新生成 -->
      <div v-if="inviteMode === 'view' && invite" class="vf-invite-dlg">
        <p class="vf-invite-dlg__hint">{{ t('problems.manage.existingInvite') }}</p>
        <n-input :value="inviteLink" readonly :placeholder="inviteLink">
          <template #suffix>
            <n-button text type="primary" size="small" @click="copyLink">{{
              t('action.copyLink')
            }}</n-button>
          </template>
        </n-input>
        <n-space justify="end">
          <n-button secondary :loading="generating" @click="inviteMode = 'generate'">
            {{ t('problems.manage.regenerate') }}
          </n-button>
        </n-space>
      </div>

      <!-- 无有效链接：选择有效期并生成 -->
      <div v-else class="vf-invite-dlg">
        <p class="vf-invite-dlg__hint">{{ t('problems.manage.expiryHint') }}</p>
        <n-space vertical :size="10">
          <n-button
            v-for="option in expiryOptions"
            :key="option.key"
            block
            :type="expiryHours === option.hours ? 'primary' : 'default'"
            :loading="generating && expiryHours === option.hours"
            @click="generateInvite(option.hours)"
          >
            {{ option.label }}
          </n-button>
        </n-space>
      </div>
    </n-modal>
  </div>
</template>

<style scoped>
/* 分栏高度由 ProblemWorkbench 内部 useSplitPane 实测锁定；
   此处仅承载邀请弹窗的排版辅助样式 */
.vf-invite-dlg {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.vf-invite-dlg__hint {
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 13px;
  line-height: 1.5;
}
</style>
