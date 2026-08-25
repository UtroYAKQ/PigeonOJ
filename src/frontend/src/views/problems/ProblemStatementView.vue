<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import {
  createProblem,
  getProblem,
  listActiveTags,
  updateProblem,
} from '@/api/problems'
import { message } from '@/utils/feedback'
import WizardShell from '@/components/WizardShell.vue'
import type { ProblemDetailEx, ProblemTagItem } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const isEdit = computed(() => Boolean(route.params.id))
const saving = ref(false)
const loading = ref(false)
const showSolution = ref(false)

const form = reactive({
  title: '',
  description: '',
  input_description: '',
  output_description: '',
  solution: '',
  /** 标签名（激活标签；≤8，docs/contracts/problems.md） */
  tags: [] as string[],
  visibility: 'public',
  time_limit_ms: 1000,
  memory_limit_mb: 256,
})
const tagOptions = ref<Array<{ label: string; value: string }>>([])

async function loadTagOptions() {
  try {
    const tags: ProblemTagItem[] = await listActiveTags()
    tagOptions.value = tags.map((item) => ({ label: item.name, value: item.name }))
  } catch {
    /* 标签加载失败不阻塞题面编辑 */
  }
}

async function loadExisting() {
  if (!isEdit.value) return
  loading.value = true
  try {
    const loaded: ProblemDetailEx = await getProblem(String(route.params.id))
    if (!loaded.can_manage) throw new Error(t('problems.create.noPermission'))
    Object.assign(form, {
      title: loaded.title,
      description: loaded.description,
      input_description: loaded.input_description ?? '',
      output_description: loaded.output_description ?? '',
      solution: loaded.solution ?? '',
      tags: [...(loaded.tags ?? [])],
      visibility: loaded.visibility ?? 'public',
      time_limit_ms: loaded.time_limit_ms,
      memory_limit_mb: loaded.memory_limit_mb,
    })
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
    router.push('/admin/problems')
  } finally {
    loading.value = false
  }
}

/** 标签上限 8：超出部分截断（契约 docs/contracts/problems.md） */
function onTagsChange(value: string[]) {
  form.tags = value.slice(0, 8)
}

function validate(): boolean {
  if (!form.title.trim() || !form.description.trim()) {
    message.error(t('problems.wizard.needStatement'))
    return false
  }
  if (!form.input_description.trim() || !form.output_description.trim()) {
    message.error(t('problems.create.ioRequired'))
    return false
  }
  return true
}

/** 下一步：持久化题面（新建则先建草稿），成功后进入「样例与测试点」页 */
async function goNext() {
  if (!validate()) return
  saving.value = true
  try {
    const payload = () => ({
      title: form.title,
      description: form.description,
      input_description: form.input_description || null,
      output_description: form.output_description || null,
      solution: form.solution || null,
      tags: form.tags,
      visibility: form.visibility,
      time_limit_ms: form.time_limit_ms,
      memory_limit_mb: form.memory_limit_mb,
    })
    let targetId: string
    if (isEdit.value) {
      targetId = String(route.params.id)
      await updateProblem(targetId, payload())
    } else {
      const created = await createProblem(payload() as Parameters<typeof createProblem>[0])
      targetId = created.id
    }
    message.success(t('problems.create.saved'))
    // 新建用 replace：浏览器后退不会回到 /new 造成重复建草稿
    const target = `/admin/problems/${targetId}/edit/cases`
    await (isEdit.value ? router.push(target) : router.replace(target))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    saving.value = false
  }
}

function cancelEdit() {
  router.push('/admin/problems')
}

onMounted(() => {
  loadTagOptions()
  loadExisting()
})

const visibilityOptions = computed(() => [
  { label: t('problems.create.visibilityPublic'), value: 'public' },
  { label: t('problems.create.visibilityPrivate'), value: 'private' },
])
</script>

<template>
  <div class="page-stack">
    <n-spin :show="loading">
      <WizardShell
        :step="1"
        :title="isEdit ? t('problems.create.editTitle') : t('problems.create.title')"
      >
        <template #actions>
          <n-button type="primary" size="small" :loading="saving" @click="goNext">
            {{ t('problems.wizard.next') }}
          </n-button>
          <n-button size="small" quaternary @click="cancelEdit">{{ t('action.cancel') }}</n-button>
        </template>

        <n-form label-placement="top" class="wizard-body">
          <n-form-item :label="t('problems.create.name')" required>
            <n-input v-model:value="form.title" size="large" />
          </n-form-item>
          <n-form-item :label="t('problems.create.statement')" required>
            <n-input v-model:value="form.description" type="textarea" :rows="10" />
          </n-form-item>
          <div class="form-grid">
            <n-form-item :label="t('problems.create.inputDescription')" required>
              <n-input v-model:value="form.input_description" type="textarea" :rows="4" />
            </n-form-item>
            <n-form-item :label="t('problems.create.outputDescription')" required>
              <n-input v-model:value="form.output_description" type="textarea" :rows="4" />
            </n-form-item>
          </div>
          <n-collapse-transition :show="showSolution">
            <n-form-item :label="t('problems.create.solution')" class="solution-field">
              <n-input v-model:value="form.solution" type="textarea" :rows="5" />
            </n-form-item>
          </n-collapse-transition>
          <n-button
            text
            size="small"
            type="primary"
            class="solution-toggle"
            @click="showSolution = !showSolution"
          >
            {{ showSolution ? t('problems.create.solutionHide') : t('problems.create.solutionToggle') }}
          </n-button>
          <div class="form-grid">
            <n-form-item :label="t('problems.create.tags')">
              <n-select
                :value="form.tags"
                multiple
                clearable
                filterable
                :options="tagOptions"
                :placeholder="t('problems.create.tagsPlaceholder')"
                @update:value="onTagsChange"
              />
            </n-form-item>
            <n-form-item :label="t('problems.create.visibility')">
              <n-select v-model:value="form.visibility" :options="visibilityOptions" />
            </n-form-item>
            <n-form-item :label="t('problems.create.timeLimit')">
              <n-input-number v-model:value="form.time_limit_ms" :min="1" class="w-full" />
            </n-form-item>
            <n-form-item :label="t('problems.create.memoryLimit')">
              <n-input-number v-model:value="form.memory_limit_mb" :min="16" class="w-full" />
            </n-form-item>
          </div>
        </n-form>
      </WizardShell>
    </n-spin>
  </div>
</template>

<style scoped>
.wizard-body {
  min-height: 320px;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}
.solution-field {
  margin-bottom: 8px;
}
.solution-toggle {
  margin-bottom: 16px;
}
.w-full {
  width: 100%;
}
@media (max-width: 760px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
