<script setup lang="ts">
/**
 * 题单新建 / 编辑信息页（管理后台共用）：元信息（标题 / 可见性）+ Markdown 介绍。
 * 题目编排走独立页面（/admin/problem-sets/:id/arrange）。
 * 创建成功 → 跳题单详情；编辑成功 → 返回详情页。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { FormInst, FormRules } from 'naive-ui'

import { createProblemSet, getProblemSet, updateProblemSet } from '@/api/problemSets'
import { message } from '@/utils/feedback'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import type { ProblemSetDetail } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

/** 编辑模式：路由带 id */
const setId = computed(() => (route.params.id ? String(route.params.id) : null))
const isEdit = computed(() => setId.value !== null)
const loading = ref(false)
const submitting = ref(false)

const formRef = ref<FormInst | null>(null)
const form = reactive({
  title: '',
  description: '',
  visibility: 'public' as 'public' | 'private',
})

const rules: FormRules = {
  title: [
    { required: true, message: t('problemSets.list.titleRequired'), trigger: ['blur', 'input'] },
  ],
}

onMounted(async () => {
  if (!isEdit.value) return
  loading.value = true
  try {
    const detail: ProblemSetDetail = await getProblemSet(setId.value!)
    form.title = detail.title
    form.description = detail.description ?? ''
    form.visibility = detail.visibility === 'team' ? 'public' : detail.visibility
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
    router.push('/admin/problem-sets')
  } finally {
    loading.value = false
  }
})

async function submit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    if (isEdit.value) {
      await updateProblemSet(setId.value!, {
        title: form.title,
        description: form.description,
        visibility: form.visibility,
      })
      message.success(t('common.success'))
      await router.push(`/admin/problem-sets/${setId.value}`)
    } else {
      const created = await createProblemSet({
        title: form.title,
        description: form.description || undefined,
        visibility: form.visibility,
      })
      message.success(t('common.success'))
      // 新建用 replace：后退不会回到空白表单重复建题单
      await router.replace(`/admin/problem-sets/${created.id}`)
    }
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    submitting.value = false
  }
}

function cancel() {
  if (isEdit.value) {
    router.push(`/admin/problem-sets/${setId.value}`)
  } else {
    router.push('/admin/problem-sets')
  }
}
</script>

<template>
  <WorkbenchShell :title="isEdit ? t('problemSets.detail.editTitle') : t('problemSets.list.createTitle')">
    <template #header-extra>
      <div class="form-actions">
        <n-button size="small" :disabled="submitting" @click="cancel">
          {{ t('action.cancel') }}
        </n-button>
        <n-button type="primary" size="small" :loading="submitting" @click="submit">
          {{ isEdit ? t('action.save') : t('problemSets.form.createAction') }}
        </n-button>
      </div>
    </template>

    <n-spin :show="loading" class="form-spin">
      <n-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-placement="top"
        class="form-grid"
      >
        <!-- 左框：元信息（标题 + 可见性 + 提示钉底）；右框：Markdown 介绍撑满 -->
        <section class="panel">
          <div class="panel__head">
            <span>{{ t('problemSets.form.basicTitle') }}</span>
          </div>
          <div class="panel__body panel__body--scroll">
            <n-form-item :label="t('problemSets.list.titleLabel')" path="title">
              <n-input
                v-model:value="form.title"
                size="large"
                :maxlength="128"
                :placeholder="t('problemSets.form.titlePlaceholder')"
              />
            </n-form-item>
            <n-form-item :label="t('problemSets.list.visibility')" path="visibility">
              <n-radio-group v-model:value="form.visibility">
                <n-radio-button value="public">
                  {{ t('problemSets.list.visibilityPublic') }}
                </n-radio-button>
                <n-radio-button value="private">
                  {{ t('problemSets.list.visibilityPrivate') }}
                </n-radio-button>
              </n-radio-group>
            </n-form-item>
            <p class="form-tip">{{ t('problemSets.form.visibilityTip') }}</p>
          </div>
          <div class="panel__foot">
          </div>
        </section>

        <section class="panel">
          <div class="panel__head">
            <span>{{ t('problemSets.list.descLabel') }}</span>
          </div>
          <div class="panel__body panel__body--flush form-desc">
            <div class="editor-fill">
              <MarkdownEditor
                v-model="form.description"
                min-height="420px"
                :placeholder="t('problemSets.form.descPlaceholder')"
              />
            </div>
          </div>
        </section>
      </n-form>
    </n-spin>
  </WorkbenchShell>
</template>

<style scoped>
.form-actions {
  display: inline-flex;
  gap: 8px;
}
/* 高度链：卡片内容区 → n-spin 两层容器 → 网格，逐级 flex:1 让双框撑满剩余视口 */
.form-spin {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.form-spin :deep(.n-spin-container),
.form-spin :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
/* 左 4 右 8 两个等高面板框：grid 默认 stretch 对齐，双框始终平齐 */
.form-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 4fr) minmax(0, 8fr);
  /* 锁定行高：内容再多也不撑破视口，超出交给框内滚动 */
  grid-template-rows: minmax(0, 1fr);
  gap: 20px;
  padding-top: 4px;
}
.panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-lg);
  background: var(--app-card-bg);
  overflow: hidden; /* 圆角裁切内部滚动区 */
}
.panel__head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  padding: 12px 20px 8px;
  font-size: 14px;
  font-weight: 600;
}
.panel__body {
  flex: 1;
  min-height: 0;
}
.panel__body--scroll {
  overflow: auto;
  padding: 4px 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.panel__body--flush {
  display: flex;
  flex-direction: column;
  padding: 12px;
}
/* 编辑器填充容器：md-editor-v3 以内联 style 设固定高度，flex/百分比都拉不动它，
   只能用绝对定位铺满父级，让它视同「父级即高度」 */
.editor-fill {
  position: relative;
  flex: 1;
  min-height: 420px;
}
.editor-fill :deep(.md-editor-shell) {
  position: absolute;
  inset: 0;
  height: auto !important;
}
.form-tip {
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}
.panel__foot {
  flex-shrink: 0;
  padding: 10px 20px 14px;
}
@media (max-width: 900px) {
  /* 窄屏：单列，两框自适应高度，不锁视口；编辑器以 min-height 420 兜底 */
  .form-spin {
    flex: none;
  }
  .form-grid {
    flex: none;
    grid-template-columns: 1fr;
  }
  .panel__body--scroll {
    overflow: visible;
  }
}
</style>
