<script setup lang="ts">
/**
 * 举报弹窗（community.md reports）：题解 / 评论等内容的举报入口。
 * 同用户同目标 pending 中重复举报由后端 3003 拦截（错误信封 message 直接透出）。
 */
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { createReport } from '@/api/community'
import ModalFooter from '@/components/ModalFooter.vue'
import { message } from '@/utils/feedback'
import type { ReportPayload } from '@/types'

const props = defineProps<{
  show: boolean
  targetType: ReportPayload['target_type']
  targetId: string
}>()
const emit = defineEmits<{ 'update:show': [boolean]; reported: [] }>()

const { t } = useI18n()
const reason = ref('')
const submitting = ref(false)

watch(
  () => props.show,
  (visible) => {
    if (visible) reason.value = ''
  },
)

async function submit() {
  const text = reason.value.trim()
  if (!text) {
    message.warning(t('community.report.reasonRequired'))
    return
  }
  submitting.value = true
  try {
    await createReport({
      target_type: props.targetType,
      target_id: props.targetId,
      reason: text,
    })
    message.success(t('community.report.success'))
    emit('update:show', false)
    emit('reported')
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.operationFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    style="width: min(480px, 92vw)"
    :title="t('community.report.title')"
    @update:show="(v: boolean) => emit('update:show', v)"
  >
    <n-input
      v-model:value="reason"
      type="textarea"
      maxlength="1000"
      show-count
      :placeholder="t('community.report.placeholder')"
      :autosize="{ minRows: 3, maxRows: 6 }"
    />
    <template #footer>
      <ModalFooter
        :loading="submitting"
        :confirm-text="t('community.report.submit')"
        @cancel="emit('update:show', false)"
        @confirm="submit"
      />
    </template>
  </n-modal>
</template>
