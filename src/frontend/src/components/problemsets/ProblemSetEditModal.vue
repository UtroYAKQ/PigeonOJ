<script setup lang="ts">
/**
 * 题单新建 / 编辑信息弹窗（管理后台共享）：problemSet 为 null 表示新建。
 * 可见性仅 public / private（团队题单随 teams 模块开放）。
 */
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { FormInst, FormRules } from 'naive-ui'

import ModalFooter from '@/components/ModalFooter.vue'
import { createProblemSet, updateProblemSet } from '@/api/problemSets'
import { message } from '@/utils/feedback'
import type { ProblemSetSummary } from '@/types'

const props = defineProps<{
  show: boolean
  /** null = 新建题单 */
  problemSet: ProblemSetSummary | null
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  saved: []
}>()

const { t } = useI18n()
const formRef = ref<FormInst | null>(null)
const submitting = ref(false)
const form = ref({ title: '', description: '', visibility: 'public' })

const rules: FormRules = {
  title: [{ required: true, message: t('problemSets.list.titleRequired'), trigger: 'blur' }],
}

watch(
  () => props.show,
  (show) => {
    if (!show) return
    form.value = props.problemSet
      ? {
          title: props.problemSet.title,
          description: props.problemSet.description ?? '',
          visibility:
            props.problemSet.visibility === 'team' ? 'public' : props.problemSet.visibility,
        }
      : { title: '', description: '', visibility: 'public' }
  },
)

async function submit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    if (props.problemSet) {
      await updateProblemSet(props.problemSet.id, {
        title: form.value.title,
        description: form.value.description,
        visibility: form.value.visibility as 'public' | 'private',
      })
    } else {
      await createProblemSet({
        title: form.value.title,
        description: form.value.description || undefined,
        visibility: form.value.visibility as 'public' | 'private',
      })
    }
    emit('update:show', false)
    message.success(t('common.success'))
    emit('saved')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    style="width: min(520px, 92vw)"
    :title="problemSet ? t('problemSets.detail.editTitle') : t('problemSets.list.createTitle')"
    @update:show="emit('update:show', $event)"
  >
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
      <n-form-item :label="t('problemSets.list.titleLabel')" path="title">
        <n-input v-model:value="form.title" :maxlength="128" @keyup.enter="submit" />
      </n-form-item>
      <n-form-item :label="t('problemSets.list.descLabel')" path="description">
        <n-input v-model:value="form.description" type="textarea" :rows="3" />
      </n-form-item>
      <n-form-item :label="t('problemSets.list.visibility')" path="visibility">
        <n-radio-group v-model:value="form.visibility">
          <n-radio value="public">{{ t('problemSets.list.visibilityPublic') }}</n-radio>
          <n-radio value="private">{{ t('problemSets.list.visibilityPrivate') }}</n-radio>
        </n-radio-group>
      </n-form-item>
    </n-form>
    <template #footer>
      <ModalFooter :loading="submitting" @cancel="emit('update:show', false)" @confirm="submit" />
    </template>
  </n-modal>
</template>
