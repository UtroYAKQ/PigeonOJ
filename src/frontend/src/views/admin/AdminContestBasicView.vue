<script setup lang="ts">
/**
 * 比赛向导 · 步骤 1 基本信息（标题 / 头像 / 说明 / 赛制 / 时间 / 封榜）。
 * 新建：/admin/contests/create；编辑：/admin/contests/:cid/edit/basic。
 * 「保存并下一步」持久化后进入编排题目页（新建用 replace 防止后退重复建赛）。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { InfoFilled } from '@element-plus/icons-vue'
import type { FormInst, FormRules } from 'naive-ui'

import { createContest, getContest, updateContest } from '@/api/contests'
import { uploadImage } from '@/api/files'
import { message } from '@/utils/feedback'
import WizardShell from '@/components/WizardShell.vue'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import type { ContestDetail } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const editingId = computed(() => (route.params.cid ? String(route.params.cid) : null))
const loading = ref(false)
const saving = ref(false)
const uploadingLogo = ref(false)
const formRef = ref<FormInst | null>(null)

const form = reactive({
  title: '',
  description: '',
  logo: '' as string | null,
  rule_type: 'ACM' as 'ACM' | 'IOI',
  start: null as number | null,
  end: null as number | null,
  regStart: null as number | null,
  regEnd: null as number | null,
  freeze: 0,
})

const rules: FormRules = {
  title: [{ required: true, message: t('contests.list.titleRequired'), trigger: 'blur' }],
}

onMounted(async () => {
  if (!editingId.value) return
  loading.value = true
  try {
    const detail: ContestDetail = await getContest(editingId.value)
    form.title = detail.title
    form.description = detail.description ?? ''
    form.logo = detail.logo ?? ''
    form.rule_type = detail.rule_type
    form.start = new Date(detail.start_time).getTime()
    form.end = new Date(detail.end_time).getTime()
    form.regStart = new Date(detail.register_start_time).getTime()
    form.regEnd = new Date(detail.register_end_time).getTime()
    form.freeze = detail.freeze_offset_seconds
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
    router.push('/admin/contests')
  } finally {
    loading.value = false
  }
})

async function onLogoChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  uploadingLogo.value = true
  try {
    const result = await uploadImage(file)
    form.logo = result.url
    message.success(t('common.success'))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.imageUploadFailed'))
  } finally {
    uploadingLogo.value = false
  }
}

function validateTimes(): boolean {
  if (form.start == null || form.end == null || form.regStart == null || form.regEnd == null) {
    message.error(t('contests.wizard.needTimes'))
    return false
  }
  if (form.start >= form.end) {
    message.error(t('contests.wizard.timeRangeInvalid'))
    return false
  }
  if (form.regStart > form.regEnd) {
    message.error(t('contests.wizard.regRangeInvalid'))
    return false
  }
  if (form.regEnd > form.end) {
    message.error(t('contests.wizard.regEndAfterEnd'))
    return false
  }
  return true
}

/** 保存并下一步：持久化比赛（新建则先创建），成功后进入编排题目页 */
async function goNext() {
  await formRef.value?.validate()
  if (!validateTimes()) return
  saving.value = true
  try {
    const meta = {
      title: form.title,
      description: form.description || null,
      logo: form.logo || null,
      rule_type: form.rule_type,
      start_time: new Date(form.start!).toISOString(),
      end_time: new Date(form.end!).toISOString(),
      register_start_time: new Date(form.regStart!).toISOString(),
      register_end_time: new Date(form.regEnd!).toISOString(),
      freeze_offset_seconds: form.freeze,
    }
    let targetId: string
    if (editingId.value) {
      targetId = editingId.value
      await updateContest(targetId, meta)
    } else {
      const created = await createContest({ ...meta, problems: [] })
      targetId = created.id
    }
    message.success(t('common.success'))
    const target = `/admin/contests/${targetId}/edit/problems`
    await (editingId.value ? router.push(target) : router.replace(target))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    saving.value = false
  }
}

function cancelWizard() {
  router.push('/admin/contests')
}
</script>

<template>
  <div class="page-fill">
    <n-spin :show="loading" class="wizard-spin">
      <WizardShell
        :step="1"
        :total="2"
        :title="editingId ? t('contests.list.editTitle') : t('contests.list.createTitle')"
      >
        <template #actions>
          <n-button type="primary" size="small" :loading="saving" @click="goNext">
            {{ t('contests.wizard.next') }}
          </n-button>
          <n-button size="small" quaternary @click="cancelWizard">{{ t('action.cancel') }}</n-button>
        </template>

        <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" class="wizard-body">
          <div class="form-hint">{{ t('contests.wizard.requiredHint') }}</div>

          <!-- 基础信息：标题通栏，头像 + 赛制 + 封榜一行 -->
          <div class="section-title">{{ t('contests.wizard.basic') }}</div>
          <n-form-item :label="t('contests.list.titleLabel')" path="title">
            <n-input v-model:value="form.title" :maxlength="128" show-count size="large" />
          </n-form-item>
          <div class="meta-row">
            <n-form-item :label="t('contests.list.logo')" class="meta-row__logo">
              <div class="logo-uploader">
                <div class="logo-preview" :class="{ empty: !form.logo }">
                  <img v-if="form.logo" :src="form.logo" alt="logo" />
                  <span v-else>{{ t('contests.list.noLogo') }}</span>
                </div>
                <div class="logo-actions">
                  <label class="logo-upload-btn">
                    <input type="file" accept="image/*" hidden @change="onLogoChange" />
                    <n-button size="small" :loading="uploadingLogo" tag="span">
                      {{ t('contests.list.logo') }}
                    </n-button>
                  </label>
                  <span class="field-hint">{{ t('contests.list.logoHint') }}</span>
                </div>
              </div>
            </n-form-item>
            <n-form-item :label="t('contests.list.ruleType')">
              <n-radio-group v-model:value="form.rule_type">
                <n-radio-button value="ACM">ACM</n-radio-button>
                <n-radio-button value="IOI">IOI</n-radio-button>
              </n-radio-group>
            </n-form-item>
            <n-form-item :label="t('contests.list.freezeOffset')" path="freeze">
              <div class="freeze-row">
                <n-input-number v-model:value="form.freeze" :min="0" style="width: 160px" />
                <n-tooltip trigger="hover" placement="top">
                  <template #trigger>
                    <n-icon size="15" class="freeze-tip"><InfoFilled /></n-icon>
                  </template>
                  {{ t('contests.list.freezeHint') }}
                </n-tooltip>
              </div>
            </n-form-item>
          </div>

          <!-- 时间安排 -->
          <div class="section-title">{{ t('contests.detail.schedule') }}</div>
          <div class="time-grid">
            <n-form-item :label="t('contests.list.startTime')">
              <n-date-picker v-model:value="form.start" type="datetime" style="width: 100%" />
            </n-form-item>
            <n-form-item :label="t('contests.list.endTime')">
              <n-date-picker v-model:value="form.end" type="datetime" style="width: 100%" />
            </n-form-item>
            <n-form-item :label="t('contests.list.regStartTime')">
              <n-date-picker v-model:value="form.regStart" type="datetime" style="width: 100%" />
            </n-form-item>
            <n-form-item :label="t('contests.list.regEndTime')">
              <n-date-picker v-model:value="form.regEnd" type="datetime" style="width: 100%" />
            </n-form-item>
          </div>

          <!-- 比赛说明：通栏 Markdown -->
          <div class="section-title">{{ t('contests.detail.about') }}</div>
          <n-form-item :label="t('contests.list.descLabel')" :show-feedback="false">
            <MarkdownEditor
              v-model="form.description"
              :placeholder="t('contests.list.descLabel')"
              min-height="240px"
            />
          </n-form-item>
        </n-form>
      </WizardShell>
    </n-spin>
  </div>
</template>

<style scoped>
/* page-fill 高度链：spin 与卡片逐层吃满，壳到底、内容区内部滚动 */
.wizard-spin {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.wizard-spin :deep(.n-spin-container),
.wizard-spin :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.wizard-spin :deep(.n-card) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.wizard-spin :deep(.n-card-content) {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
/* 分节标题：与比赛详情面板同款主色短竖条 */
.section-title {
  margin: 6px 0 10px;
  font-size: 13px;
  font-weight: 650;
  color: var(--app-text);
  display: flex;
  align-items: center;
  gap: 8px;
}
.section-title::before {
  content: '';
  width: 3px;
  height: 14px;
  border-radius: 2px;
  background: var(--app-primary);
}
/* 头像 + 赛制 + 封榜 一行排布，底对齐避免表单反馈高度不齐 */
.meta-row {
  display: flex;
  gap: 48px;
  align-items: flex-start;
  flex-wrap: wrap;
}
.meta-row__logo {
  flex-shrink: 0;
}
.logo-uploader {
  display: flex;
  gap: 16px;
  align-items: center;
}
.logo-preview {
  width: 96px;
  height: 96px;
  border-radius: 10px;
  border: 1px solid var(--app-border);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--app-muted-bg);
  color: var(--app-text-secondary);
  font-size: 12px;
  flex-shrink: 0;
}
.logo-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.logo-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.logo-upload-btn {
  display: inline-block;
  cursor: pointer;
}
.time-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0 16px;
}
@media (max-width: 1100px) {
  .time-grid {
    grid-template-columns: 1fr 1fr;
  }
}
.field-hint {
  margin-left: 8px;
  color: var(--app-text-secondary);
  font-size: 12px;
}
.freeze-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.freeze-tip {
  color: var(--app-text-secondary);
  cursor: help;
  margin-top: 2px;
}
</style>
