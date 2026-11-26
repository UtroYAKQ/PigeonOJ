<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ImagePlus, Info, Loader2 } from '@lucide/vue'

import { createContest, getContest, updateContest } from '@/api/contests'
import { uploadImage } from '@/api/files'
import { createTeamContest, getTeamContest, updateTeamContest } from '@/api/teams'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import MarkdownEditor from '@/components/common/MarkdownEditor.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { TooltipHint } from '@/components/ui/tooltip'
import { message } from '@/utils/feedback'
import type { ContestCreatePayload, ContestRuleType } from '@/types'
import DateTimeField from '@/components/common/DateTimeField.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const editingId = computed(() => (route.params.cid ? String(route.params.cid) : null))
const teamId = computed(() => (route.params.teamId ? String(route.params.teamId) : null))
const listPath = computed(() => (teamId.value ? `/teams/${teamId.value}` : '/admin/contests'))

function arrangePath(id: string): string {
  return teamId.value
    ? `/teams/${teamId.value}/contests/${id}/edit/problems`
    : `/admin/contests/${id}/edit/problems`
}

const loading = ref(false)
const saving = ref(false)
const uploadingLogo = ref(false)
const logoInput = ref<HTMLInputElement>()

const form = reactive({
  title: '',
  description: '',
  logo: '' as string | null,
  rule_type: 'ACM' as ContestRuleType,
  start: null as number | null,
  end: null as number | null,
  regStart: null as number | null,
  regEnd: null as number | null,
  /** 封榜时间（绝对时刻；null = 不封榜） */
  freezeAt: null as number | null,
})

const timeFields = [
  { key: 'start', label: 'contests.list.startTime' },
  { key: 'end', label: 'contests.list.endTime' },
  { key: 'regStart', label: 'contests.list.regStartTime' },
  { key: 'regEnd', label: 'contests.list.regEndTime' },
] as const

const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
const MAX_IMAGE_BYTES = 5 * 1024 * 1024

function setRuleType(value: unknown): void {
  form.rule_type = String(value) as ContestRuleType
}

onMounted(async () => {
  if (!editingId.value) return
  loading.value = true
  try {
    const detail = await (teamId.value
      ? getTeamContest(teamId.value, editingId.value)
      : getContest(editingId.value))
    form.title = detail.title
    form.description = detail.description ?? ''
    form.logo = detail.logo ?? ''
    form.rule_type = detail.rule_type
    form.start = new Date(detail.start_time).getTime()
    form.end = new Date(detail.end_time).getTime()
    form.regStart = new Date(detail.register_start_time).getTime()
    form.regEnd = new Date(detail.register_end_time).getTime()
    form.freezeAt = detail.freeze_time ? new Date(detail.freeze_time).getTime() : null
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
    void router.push(listPath.value)
  } finally {
    loading.value = false
  }
})

function pickLogo(): void {
  logoInput.value?.click()
}

async function onLogoChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!IMAGE_TYPES.includes(file.type)) {
    message.error(t('common.imageTypeInvalid'))
    return
  }
  if (file.size > MAX_IMAGE_BYTES) {
    message.error(t('common.imageTooLarge'))
    return
  }
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
  // 封榜时间（选填）：须晚于开始、不晚于结束（后端 CHECK 同口径兜底）
  if (form.freezeAt != null && (form.freezeAt <= form.start || form.freezeAt > form.end)) {
    message.error(t('contests.wizard.freezeRangeInvalid'))
    return false
  }
  return true
}

/** 保存并下一步：持久化比赛（新建则先创建），成功后进入编排题目页 */
async function goNext(): Promise<void> {
  if (saving.value) return
  const title = form.title.trim()
  if (!title) {
    message.error(t('contests.list.titleRequired'))
    return
  }
  if (!validateTimes()) return

  saving.value = true
  try {
    const body: ContestCreatePayload = {
      title,
      description: form.description || null,
      logo: form.logo || null,
      rule_type: form.rule_type,
      start_time: new Date(form.start!).toISOString(),
      end_time: new Date(form.end!).toISOString(),
      register_start_time: new Date(form.regStart!).toISOString(),
      register_end_time: new Date(form.regEnd!).toISOString(),
      // 封榜时间：null = 不封榜（清空选择器即取消封榜）
      freeze_time: form.freezeAt == null ? null : new Date(form.freezeAt).toISOString(),
    }

    let targetId: string
    if (editingId.value) {
      targetId = editingId.value
      await (teamId.value
        ? updateTeamContest(teamId.value, targetId, body)
        : updateContest(targetId, body))
    } else {
      const created = await (teamId.value
        ? createTeamContest(teamId.value, { ...body, problems: [] })
        : createContest({ ...body, problems: [] }))
      targetId = created.id
    }

    message.success(t('common.success'))
    const target = arrangePath(targetId)
    // 新建用 replace：防止后退回到创建页重复建赛
    if (editingId.value) await router.push(target)
    else await router.replace(target)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    saving.value = false
  }
}

function cancelWizard(): void {
  void router.push(listPath.value)
}
</script>

<template>
  <div class="mx-auto w-full max-w-[1200px] px-4 pb-12 pt-4 sm:px-6">
    <header class="flex flex-wrap items-center gap-2">
      <h1 class="text-xl font-semibold leading-tight tracking-tight">
        {{ editingId ? t('contests.list.editTitle') : t('contests.list.createTitle') }}
      </h1>
      <span class="text-[12px] font-medium text-muted-foreground">1 / 2</span>
    </header>

    <div v-if="loading" class="grid min-h-[360px] place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <!-- 无卡片表单：分区标题 + 细分隔线 + 字段说明，仿 shadcn 设置页 -->
    <form v-else class="mt-5 space-y-8" @submit.prevent="goNext">
      <section>
        <h2 class="text-lg font-medium">{{ t('contests.wizard.basic') }}</h2>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('contests.wizard.requiredHint') }}
        </p>
        <div class="my-5 h-px bg-border" role="separator" />

        <div class="space-y-8">
          <div class="grid gap-2">
            <div class="flex items-center justify-between">
              <Label for="contest-title" class="text-sm font-medium">
                {{ t('contests.list.titleLabel') }}
                <span class="text-destructive">*</span>
              </Label>
              <span class="text-[11px] tabular-nums text-muted-foreground">
                {{ form.title.length }}/128
              </span>
            </div>
            <Input
              id="contest-title"
              :model-value="form.title"
              :maxlength="128"
              class="h-10 text-sm"
              @update:model-value="(value) => (form.title = String(value))"
            />
            <p class="text-[13px] leading-5 text-muted-foreground">
              {{ t('contests.wizard.titleHint') }}
            </p>
          </div>

          <div class="grid gap-6 md:grid-cols-3">
            <div class="grid gap-2">
              <Label class="text-sm font-medium">{{ t('contests.list.logo') }}</Label>
              <div class="flex flex-wrap items-center gap-4">
                <BaseAvatar
                  kind="contest"
                  :src="form.logo"
                  :name="form.title || null"
                  :size="64"
                  :round="false"
                  :radius="12"
                  bordered
                />
                <Button type="button" variant="outline" :disabled="uploadingLogo" @click="pickLogo">
                  <Loader2 v-if="uploadingLogo" class="size-4 animate-spin" />
                  <ImagePlus v-else class="size-4" />
                  {{ form.logo ? t('action.change') : t('action.upload') }}
                </Button>
                <input
                  ref="logoInput"
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  class="hidden"
                  @change="onLogoChange"
                />
              </div>
              <p class="text-[13px] leading-5 text-muted-foreground">
                {{ t('contests.list.logoHint') }}
              </p>
            </div>

            <div class="grid gap-2">
              <Label class="text-sm font-medium">{{ t('contests.list.ruleType') }}</Label>
              <Select :model-value="form.rule_type" @update:model-value="setRuleType">
                <SelectTrigger class="h-10 w-full text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ACM">ACM</SelectItem>
                  <SelectItem value="IOI">IOI</SelectItem>
                </SelectContent>
              </Select>
              <p class="text-[13px] leading-5 text-muted-foreground">
                {{ t('contests.wizard.ruleHint') }}
              </p>
            </div>

            <div class="grid gap-2">
              <div class="flex items-center gap-1.5">
                <Label class="text-sm font-medium">{{ t('contests.list.freezeAt') }}</Label>
                <TooltipHint :text="t('contests.list.freezeHint')">
                  <span tabindex="0" class="inline-flex text-muted-foreground">
                    <Info class="size-3.5" />
                  </span>
                </TooltipHint>
              </div>
              <DateTimeField v-model="form.freezeAt" />
              <p class="text-[13px] leading-5 text-muted-foreground">
                {{ t('contests.list.freezeHint') }}
              </p>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div class="h-px bg-border" role="separator" />
        <h2 class="pt-8 text-lg font-medium">{{ t('contests.detail.schedule') }}</h2>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('contests.wizard.timeHint') }}
        </p>
        <div class="my-5 h-px bg-border" role="separator" />
        <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div v-for="field in timeFields" :key="field.key" class="grid gap-2">
            <Label :for="`contest-${field.key}`" class="text-sm font-medium">
              {{ t(field.label) }}
              <span class="text-destructive">*</span>
            </Label>
            <DateTimeField
              :id="`contest-${field.key}`"
              :model-value="form[field.key]"
              @update:model-value="(value) => (form[field.key] = value)"
            />
          </div>
        </div>
      </section>

      <section>
        <div class="h-px bg-border" role="separator" />
        <h2 class="pt-8 text-lg font-medium">{{ t('contests.detail.about') }}</h2>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('contests.list.descLabel') }}
        </p>
        <div class="my-5 h-px bg-border" role="separator" />
        <MarkdownEditor
          v-model="form.description"
          :placeholder="t('contests.list.descLabel')"
          min-height="320px"
        />
      </section>

      <div class="flex flex-wrap justify-start gap-2 pt-2">
        <Button type="submit" :disabled="saving || loading">
          <Loader2 v-if="saving" class="size-4 animate-spin" />
          {{ t('contests.wizard.next') }}
        </Button>
        <Button type="button" variant="outline" @click="cancelWizard">
          {{ t('action.cancel') }}
        </Button>
      </div>
    </form>
  </div>
</template>
