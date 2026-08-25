<script setup lang="ts">
/**
 * 发布与验题工作台（编辑向导第三步）：
 * 左栏题目预览、右栏代码编辑器；右上「邀请验题」选择有效期后
 * 生成链接并复制。自行验题以当前账号提交，按正式测试点判题。
 * 发布门禁以后端 needs_reverification 为准。
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Key } from '@element-plus/icons-vue'

import { initVerification, publishProblem, submitVerifyCode } from '@/api/problems'
import type { ProblemDetailEx, ProblemLanguage } from '@/types'
import { dialog, message } from '@/utils/feedback'
import { languageOptions } from '@/constants/languages'
import { copyToClipboard } from '@/utils/clipboard'
import CodeEditor from '@/components/CodeEditor.vue'
import ProblemMetaBar from '@/components/problem/ProblemMetaBar.vue'
import ProblemStatement from '@/components/problem/ProblemStatement.vue'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{ problem: ProblemDetailEx }>()
const emit = defineEmits<{ refresh: []; published: [] }>()

const router = useRouter()
const { t } = useI18n()

const generating = ref(false)
const publishing = ref(false)
const invitePopover = ref(false)
const expiryHours = ref<24 | 72 | 168>(72)
const invite = ref<{ token: string; expires_at: string | null } | null>(null)

// 自行验题
const language = ref<ProblemLanguage>('cpp17')
const code = ref('')
const submitting = ref(false)

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

async function generateInvite(hours: 24 | 72 | 168) {
  if (generating.value) return
  generating.value = true
  expiryHours.value = hours
  try {
    const res = await initVerification(props.problem.id, {
      invite_expires_hours: hours,
    })
    invite.value = res.invite ?? null
    invitePopover.value = false
    message.success(t('common.success'))
  } catch (error) {
    // 已有进行中的验题（3003）等业务错误直接透出
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

// 发布动作由外层卡片头承载（ProblemVerifyView 经 WizardShell actions 插槽放置），经模板 ref 调用
defineExpose({ publish, blocked, publishing })
</script>

<template>
  <div class="vp-split">
    <!-- 左：题目预览（题面展示与详情页共用同一组件，样例交互保持一致） -->
    <section class="vp-statement" aria-label="problem statement">
      <ProblemMetaBar :problem="problem" show-title />
      <div class="vp-body">
        <ProblemStatement :problem="problem" :show-solution="false" />
      </div>
    </section>

    <!-- 右：验题代码编辑器 -->
    <section class="vp-work">
      <div class="vp-toolbar">
        <n-tag size="small" round :type="stateTagType">{{ stateText }}</n-tag>
        <div class="vp-toolbar__spacer" />
        <n-select v-model:value="language" :options="languageOptions" class="vp-lang" />
        <n-popover v-model:show="invitePopover" trigger="click" placement="bottom-end">
          <template #trigger>
            <n-button secondary :loading="generating">
              <template #icon><n-icon :component="Key" /></template>
              {{ t('problems.manage.inviteVerify') }}
            </n-button>
          </template>
          <div class="vp-popover">
            <p class="vp-popover__label">{{ t('problems.manage.expiry') }}</p>
            <n-button
              v-for="option in expiryOptions"
              :key="option.key"
              size="small"
              block
              :loading="generating && expiryHours === option.hours"
              @click="generateInvite(option.hours)"
            >
              {{ option.label }}
            </n-button>
          </div>
        </n-popover>
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

      <!-- 邀请链接条：生成后常驻展示，一键复制 -->
      <div v-if="invite" class="vp-invite">
        <n-input :value="inviteLink" readonly size="small">
          <template #suffix>
            <n-button text type="primary" size="tiny" @click="copyLink">{{
              t('action.copyLink')
            }}</n-button>
          </template>
        </n-input>
      </div>

      <div class="vp-editor">
        <CodeEditor v-model="code" :language="language" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.vp-split {
  display: grid;
  grid-template-columns: minmax(0, 5fr) minmax(0, 6fr);
  align-items: stretch;
  /* 由外层 verify-stage 决定高度：左右栏满高，编辑器 flex:1 吃掉右栏剩余 */
  height: 100%;
}
/* 左栏：独立滚动（高度由外层 stage 拉伸决定，不再固定 vh）。
   分栏以右栏发丝线分界，线两侧各留 16px，左短内容时不显空 */
.vp-statement {
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  padding-right: 16px;
}
.vp-body {
  margin-top: 14px;
}

/* 右栏：工具行 + 链接条 + 编辑器；左侧发丝线与左栏分界 */
.vp-work {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  border-left: 1px solid var(--app-border);
  padding-left: 16px;
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
.vp-popover {
  display: grid;
  gap: 8px;
  width: 180px;
}
.vp-popover__label {
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 13px;
}
.vp-editor {
  flex: 1;
  /* 保底不低于原固定高度；视口更大时随 flex 继续增长 */
  min-height: 46vh;
}
@media (max-width: 900px) {
  .vp-split {
    grid-template-columns: 1fr;
    height: auto; /* 单列堆叠时按内容自然高度 */
  }
  .vp-statement {
    padding-right: 0;
    max-height: 60vh;
    overflow-y: auto;
  }
  .vp-work {
    border-left: none;
    padding-left: 0;
  }
  .vp-editor {
    height: 60vh;
    min-height: 320px;
    flex: none;
  }
}
</style>
