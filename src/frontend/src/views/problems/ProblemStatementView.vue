<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { createProblem, getProblem, listActiveTags, updateProblem } from '@/api/problems'
import { message } from '@/utils/feedback'
import WizardShell from '@/components/WizardShell.vue'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import type { ProblemDetail, ProblemTagItem } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const isEdit = computed(() => Boolean(route.params.id))
const saving = ref(false)
const loading = ref(false)
const showSolution = ref(false)

const form = reactive({
  title: '',
  background: '',
  description: '',
  input_description: '',
  output_description: '',
  note: '',
  solution: '',
  /** 标签名（激活标签；≤8，docs/contracts/problems.md） */
  tags: [] as string[],
  visibility: 'public',
  time_limit_ms: 1000,
  memory_limit_mb: 256,
  /** 难度分（手动填写；null = 未评分） */
  difficulty: null as number | null,
})
const tagOptions = ref<Array<{ label: string; value: string }>>([])
/** 官方题解编辑器懒挂载：首次展开折叠面板时才创建编辑器实例 */
const solutionMounted = ref(false)
/** 题面说明（可选）：与官方题解同款折叠交互 */
const showNote = ref(false)
const noteMounted = ref(false)

function toggleNote() {
  showNote.value = !showNote.value
  if (showNote.value) noteMounted.value = true
}

function toggleSolution() {
  showSolution.value = !showSolution.value
  if (showSolution.value) solutionMounted.value = true
}

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
    const loaded: ProblemDetail = await getProblem(String(route.params.id))
    if (!loaded.can_manage) throw new Error(t('problems.create.noPermission'))
    Object.assign(form, {
      title: loaded.title,
      background: loaded.background,
      description: loaded.description,
      input_description: loaded.input_description ?? '',
      output_description: loaded.output_description ?? '',
      note: loaded.note ?? '',
      solution: loaded.solution ?? '',
      tags: [...(loaded.tags ?? [])],
      visibility: loaded.visibility ?? 'public',
      time_limit_ms: loaded.time_limit_ms,
      memory_limit_mb: loaded.memory_limit_mb,
      difficulty: loaded.difficulty ?? null,
    })
    // 已有说明时默认展开编辑器
    if (form.note) {
      showNote.value = true
      noteMounted.value = true
    }
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
  if (!form.title.trim() || !form.background.trim() || !form.description.trim()) {
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
      background: form.background,
      description: form.description,
      input_description: form.input_description || null,
      output_description: form.output_description || null,
      // 空字符串 = 清空说明（后端 PUT 语义："" 置 NULL）
      note: form.note,
      solution: form.solution || null,
      tags: form.tags,
      visibility: form.visibility,
      time_limit_ms: form.time_limit_ms,
      memory_limit_mb: form.memory_limit_mb,
      difficulty: form.difficulty,
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
          <div class="form-hint">{{ t('problems.create.requiredHint') }}</div>

          <!-- 基础信息：标题 + 低频元数据（标签 / 可见性 / 限制）合并为一行区，压缩纵向空间 -->
          <div class="section-title">{{ t('problems.create.sectionBasic') }}</div>
          <n-form-item :label="t('problems.create.name')" required>
            <n-input v-model:value="form.title" size="large" />
          </n-form-item>
          <div class="meta-grid">
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
            <n-form-item :label="t('problems.create.difficulty')">
              <n-input-number
                v-model:value="form.difficulty"
                :min="0"
                clearable
                :placeholder="t('problems.create.difficultyPlaceholder')"
                class="w-full"
              />
            </n-form-item>
          </div>

          <!-- 题面内容：页面主体，编辑器沉到元数据之后，形成自上而下的书写动线 -->
          <div class="section-title section-gap">{{ t('problems.create.sectionStatement') }}</div>
          <n-form-item :label="t('problems.create.background')" required>
            <MarkdownEditor v-model="form.background" min-height="180px" compact />
          </n-form-item>
          <n-form-item :label="t('problems.create.statement')" required>
            <MarkdownEditor v-model="form.description" min-height="360px" />
          </n-form-item>
          <div class="form-grid">
            <n-form-item :label="t('problems.create.inputDescription')" required>
              <MarkdownEditor v-model="form.input_description" min-height="180px" compact />
            </n-form-item>
            <n-form-item :label="t('problems.create.outputDescription')" required>
              <MarkdownEditor v-model="form.output_description" min-height="180px" compact />
            </n-form-item>
          </div>

          <!-- 题面说明：可选题面要素，渲染于题面最后；与官方题解同款折叠交互 -->
          <div class="solution-head">
            <span class="section-title">{{ t('problems.create.note') }}</span>
            <n-button text size="small" type="primary" @click="toggleNote">
              {{ showNote ? t('problems.create.noteHide') : t('problems.create.noteAdd') }}
            </n-button>
          </div>
          <n-collapse-transition :show="showNote">
            <n-form-item v-if="noteMounted" :show-feedback="false" class="solution-field">
              <MarkdownEditor v-model="form.note" min-height="160px" compact />
            </n-form-item>
          </n-collapse-transition>

          <!-- 官方题解：分区头 + 右侧展开入口；首次展开才挂载编辑器（避免在 0 高折叠容器中初始化） -->
          <div class="solution-head">
            <span class="section-title">{{ t('problems.create.solution') }}</span>
            <n-button text size="small" type="primary" @click="toggleSolution">
              {{
                showSolution ? t('problems.create.solutionHide') : t('problems.create.solutionAdd')
              }}
            </n-button>
          </div>
          <n-collapse-transition :show="showSolution">
            <n-form-item v-if="solutionMounted" :show-feedback="false" class="solution-field">
              <MarkdownEditor v-model="form.solution" min-height="200px" />
            </n-form-item>
          </n-collapse-transition>
        </n-form>
      </WizardShell>
    </n-spin>
  </div>
</template>

<style scoped>
.wizard-body {
  min-height: 320px;
}
.form-hint {
  margin-bottom: 4px;
  color: var(--app-text-secondary);
  font-size: 12px;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}
/* 基础信息元数据行：桌面四列一行放下，窄屏逐级降列 */
.meta-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0 12px;
}
.section-gap {
  margin-top: 20px;
}
.solution-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 20px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--app-border);
}
.solution-head .section-title {
  margin: 0;
}
.solution-field {
  margin-top: 4px;
}
.w-full {
  width: 100%;
}
@media (max-width: 960px) {
  .meta-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 760px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 560px) {
  .meta-grid {
    grid-template-columns: 1fr;
  }
}
</style>
