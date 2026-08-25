<script setup lang="ts">
/**
 * 验题工作台右栏（编辑向导第三步）：状态标签 + 语言选择 + 代码编辑器，
 * 右上「邀请验题」选择有效期后生成链接并复制。自行验题以当前账号提交，
 * 按正式测试点判题。发布门禁以后端 needs_reverification 为准。
 * 分栏布局与左栏题面由 ProblemVerifyView 承载（与邀请验题落地页同款平铺风）。
 */
import { computed, h, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Key } from '@element-plus/icons-vue'
import type { DataTableColumns } from 'naive-ui'

import { getVerifyInvite, initVerification, publishProblem, submitVerifyCode } from '@/api/problems'
import { listSubmissions } from '@/api/judge'
import type { ProblemDetailEx, ProblemLanguage, Submission } from '@/types'
import { dialog, message } from '@/utils/feedback'
import { languageOptions } from '@/constants/languages'
import { copyToClipboard } from '@/utils/clipboard'
import CodeEditor from '@/components/CodeEditor.vue'
import StatusTag from '@/components/StatusTag.vue'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{ problem: ProblemDetailEx }>()
const emit = defineEmits<{ refresh: []; published: [] }>()

const router = useRouter()
const { t } = useI18n()

const generating = ref(false)
const publishing = ref(false)
const inviteDialog = ref(false)
const inviteLoading = ref(false)
const inviteMode = ref<'generate' | 'view'>('generate')
const expiryHours = ref<24 | 72 | 168>(72)
const invite = ref<{ token: string; expires_at: string | null } | null>(null)

// 自行验题
const language = ref<ProblemLanguage>('cpp17')
const code = ref('')
const submitting = ref(false)

// 验题提交记录（本人该题的 verify 类型提交，弹窗内点击行跳评测结果页）
const subsDialog = ref(false)
const subsLoading = ref(false)
const verifySubs = ref<Submission[]>([])

async function openSubsDialog() {
  if (subsLoading.value) return
  subsLoading.value = true
  subsDialog.value = true
  try {
    const result = await listSubmissions({ problem_id: props.problem.id, page_size: 50 })
    verifySubs.value = result.items.filter((item) => item.submit_type === 'verify')
  } catch {
    verifySubs.value = []
  } finally {
    subsLoading.value = false
  }
}

function openSubmissionRow(row: Submission) {
  router.push(`/problems/${props.problem.id}/submissions/${row.id}`)
}

const subColumns = computed<DataTableColumns<Submission>>(() => [
  {
    title: t('problems.detail.status'),
    key: 'status',
    minWidth: 110,
    render: (row) => h(StatusTag, { status: row.status }),
  },
  { title: t('problems.detail.language'), key: 'language', width: 100 },
  { title: t('problems.submission.score'), key: 'score', width: 70 },
  {
    title: t('problems.submission.time'),
    key: 'time_used_ms',
    width: 100,
    render: (row) => `${row.time_used_ms ?? '-'} ms`,
  },
  {
    title: t('problems.manage.submittedAt'),
    key: 'created_at',
    minWidth: 140,
    render: (row) => formatDateTime(row.created_at),
  },
  {
    title: t('problems.manage.viewSubmission'),
    key: 'actions',
    width: 70,
    render: (row) =>
      h(
        'a',
        {
          class: 'vp-subs__link',
          onClick: () => openSubmissionRow(row),
        },
        t('problems.manage.viewSubmission'),
      ),
  },
])

type VerifyState = 'verified' | 'stale' | 'unverified'

const state = computed<VerifyState>(() => {
  if (!props.problem.is_verified) return 'unverified'
  return props.problem.needs_reverification ? 'stale' : 'verified'
})

const stateTagType = computed(() =>
  state.value === 'verified' ? 'success' : state.value === 'stale' ? 'warning' : 'default',
)
const stateText = computed(() => {
  if (state.value === 'verified')
    return props.problem.verified_at
      ? t('problems.manage.verifiedAt', { time: formatDateTime(props.problem.verified_at) })
      : t('problems.manage.verifiedTag')
  if (state.value === 'stale') return t('problems.manage.reverifyRequired')
  return t('problems.manage.notVerified')
})

const blocked = computed(
  () => !props.problem.is_verified || Boolean(props.problem.needs_reverification),
)

const inviteLink = computed(() =>
  invite.value ? `${window.location.origin}/verify/${invite.value.token}` : '',
)

const expiryOptions = computed(() => [
  { key: '24', label: t('problems.manage.expiry24'), hours: 24 as const },
  { key: '72', label: t('problems.manage.expiry72'), hours: 72 as const },
  { key: '168', label: t('problems.manage.expiry168'), hours: 168 as const },
])

/** 确保存在进行中的验题记录（已有 pending 时忽略 3003 直接尝试提交） */
async function ensureSelfVerification() {
  try {
    await initVerification(props.problem.id, {})
  } catch {
    /* 已有进行中的验题（3003）等场景：交由提交接口给出最终错误 */
  }
}

async function submitSelfVerify() {
  if (!code.value.trim()) return
  submitting.value = true
  try {
    await ensureSelfVerification()
    const res = await submitVerifyCode(props.problem.id, {
      code: code.value,
      language: language.value,
    })
    message.success(t('problems.verify.submitted'))
    router.push(`/problems/${props.problem.id}/submissions/${res.submission_id}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    submitting.value = false
  }
}

/** 先查现有链接、确定展示模式后再开弹窗，避免弹出后内容跳变 */
async function openInviteDialog() {
  if (inviteLoading.value) return
  inviteLoading.value = true
  try {
    const existing = await getVerifyInvite(props.problem.id)
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
    const res = await initVerification(props.problem.id, {
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

function publish() {
  dialog.warning({
    title: t('problems.detail.publish'),
    content: t('problems.manage.publishConfirm'),
    positiveText: t('problems.detail.publish'),
    negativeText: t('action.cancel'),
    onPositiveClick: async () => {
      publishing.value = true
      try {
        await publishProblem(props.problem.id)
        message.success(t('problems.detail.publishSuccess'))
        emit('refresh')
        emit('published')
      } catch (error) {
        message.error(error instanceof Error ? error.message : t('common.operationFailed'))
      } finally {
        publishing.value = false
      }
    },
  })
}

// 发布动作由页头承载（ProblemVerifyView 经模板 ref 调用）
defineExpose({ publish, blocked, publishing })
</script>

<template>
  <!-- 右栏工作台：工具行 + 编辑器；高度由外层网格拉伸（align-items: stretch）决定 -->
  <section class="vp-work" aria-label="verify workbench">
    <div class="vp-toolbar">
      <n-tag size="small" round :type="stateTagType">{{ stateText }}</n-tag>
      <div class="vp-toolbar__spacer" />
      <n-select v-model:value="language" :options="languageOptions" class="vp-lang" />
      <n-button secondary :loading="subsLoading && subsDialog" @click="openSubsDialog">
        {{ t('problems.manage.verifySubmissions') }}
      </n-button>
      <n-button secondary @click="openInviteDialog">
        <template #icon><n-icon :component="Key" /></template>
        {{ t('problems.manage.inviteVerify') }}
      </n-button>
      <n-button
        type="primary"
        secondary
        :loading="submitting"
        :disabled="!code.trim()"
        @click="submitSelfVerify"
      >
        {{ t('problems.selfVerify.submit') }}
      </n-button>
    </div>

    <div class="vp-editor">
      <CodeEditor v-model="code" :language="language" />
    </div>
  </section>

  <n-modal
    v-model:show="subsDialog"
    preset="card"
    :title="t('problems.manage.verifySubmissions')"
    style="width: min(760px, 94vw)"
  >
    <n-data-table
      v-if="verifySubs.length"
      size="small"
      :columns="subColumns"
      :data="verifySubs"
      :row-props="(row: Submission) => ({ style: 'cursor: pointer;', onClick: () => openSubmissionRow(row) })"
    />
    <n-empty v-else :description="t('common.noData')" />
  </n-modal>

  <n-modal
    v-model:show="inviteDialog"
    preset="card"
    :title="t('problems.manage.inviteDialogTitle')"
    style="max-width: 460px"
  >
    <!-- 已存在有效链接：直接展示，可复制或重新生成 -->
    <div v-if="inviteMode === 'view' && invite" class="vp-invite-dlg">
      <p class="vp-invite-dlg__hint">{{ t('problems.manage.existingInvite') }}</p>
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
    <div v-else class="vp-invite-dlg">
      <p class="vp-invite-dlg__hint">{{ t('problems.manage.expiryHint') }}</p>
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
</template>

<style scoped>
/* 右栏：工具行 + 编辑器（min-height:0 让 flex 正确压缩，编辑器随剩余高度伸缩） */
.vp-work {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  min-height: 0;
  padding-left: 10px;
}
.vp-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.vp-toolbar__spacer {
  flex: 1;
}
.vp-lang {
  width: 160px;
}
.vp-editor {
  flex: 1;
  min-height: 0;
}
.vp-invite-dlg {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.vp-invite-dlg__hint {
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 13px;
  line-height: 1.5;
}
.vp-subs__link {
  color: var(--app-primary);
  cursor: pointer;
}
.vp-subs__link:hover {
  text-decoration: underline;
}

@media (max-width: 899px) {
  .vp-work {
    padding-left: 0;
    margin-top: 14px;
  }
  .vp-editor {
    height: 60vh; /* 窄屏堆叠时给编辑器固定可视高度 */
    min-height: 320px;
    flex: none;
  }
}
</style>
