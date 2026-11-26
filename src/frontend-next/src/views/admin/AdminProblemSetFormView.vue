<script setup lang="ts">
/**
 * 题单新建 / 编辑信息页（管理后台共用）：元信息（标题 / 可见性）+ Markdown 介绍。
 * 题目编排走独立的题单详情页（/admin/problem-sets/:id）。
 * 创建成功 → 跳题单详情；编辑成功 → 返回详情页。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { createProblemSet, getProblemSet, updateProblemSet } from '@/api/problemSets'
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
import { message } from '@/utils/feedback'
import type { ProblemSetDetail } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

/** 编辑模式：路由带 id */
const setId = computed(() => (route.params.id ? String(route.params.id) : null))
const isEdit = computed(() => setId.value !== null)
const loading = ref(false)
const submitting = ref(false)

const form = reactive({
  title: '',
  description: '',
  visibility: 'public' as 'public' | 'private',
})

function onVisibilityChange(value: unknown): void {
  form.visibility = String(value) === 'private' ? 'private' : 'public'
}

onMounted(async () => {
  if (!isEdit.value) return
  loading.value = true
  try {
    const detail: ProblemSetDetail = await getProblemSet(setId.value!)
    form.title = detail.title
    form.description = detail.description ?? ''
    // 全站题单仅 public/private；团队分支值不会出现在管理端点，防御性兜底为 public
    form.visibility = detail.visibility === 'public' ? 'public' : 'private'
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
    void router.push('/admin/problem-sets')
  } finally {
    loading.value = false
  }
})

async function submit(): Promise<void> {
  if (!form.title.trim()) {
    message.warning(t('problemSets.list.titleRequired'))
    return
  }
  if (submitting.value) return
  submitting.value = true
  try {
    if (isEdit.value) {
      await updateProblemSet(setId.value!, {
        title: form.title.trim(),
        description: form.description,
        visibility: form.visibility,
      })
      message.success(t('common.success'))
      await router.push(`/admin/problem-sets/${setId.value}`)
    } else {
      const created = await createProblemSet({
        title: form.title.trim(),
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

function cancel(): void {
  router.push(isEdit.value ? `/admin/problem-sets/${setId.value}` : '/admin/problem-sets')
}
</script>

<template>
  <div class="mx-auto w-full max-w-[1200px] px-4 pb-12 pt-4 sm:px-6">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div class="min-w-0">
        <h1 class="text-xl font-semibold leading-tight tracking-tight">
          {{ isEdit ? t('problemSets.detail.editTitle') : t('problemSets.list.createTitle') }}
        </h1>
        <p class="mt-2 text-sm leading-5 text-muted-foreground">{{ t('problemSets.form.hint') }}</p>
      </div>
    </header>

    <div class="my-5 h-px bg-border" role="separator" />

    <div v-if="loading" class="grid h-[320px] place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <!-- 平铺无框表单：与新建题目页一致 -->
    <form v-else class="space-y-8" @submit.prevent="submit">
      <section>
        <h2 class="text-lg font-medium">{{ t('problemSets.form.basicTitle') }}</h2>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('problemSets.form.basicHint') }}
        </p>
        <div class="my-5 h-px bg-border" role="separator" />

        <div class="space-y-8">
          <div class="grid gap-2">
            <div class="flex items-center justify-between">
              <Label for="problem-set-title" class="text-sm font-medium">
                {{ t('problemSets.list.titleLabel') }}
                <span class="text-destructive">*</span>
              </Label>
              <span class="text-[11px] tabular-nums text-muted-foreground">
                {{ form.title.length }}/128
              </span>
            </div>
            <Input
              id="problem-set-title"
              v-model="form.title"
              :maxlength="128"
              :placeholder="t('problemSets.form.titlePlaceholder')"
              class="h-10 text-sm"
            />
            <p class="text-[13px] leading-5 text-muted-foreground">
              {{ t('problemSets.form.titleHint') }}
            </p>
          </div>

          <div class="grid gap-2">
            <Label class="text-sm font-medium">{{ t('problemSets.list.visibility') }}</Label>
            <Select :model-value="form.visibility" @update:model-value="onVisibilityChange">
              <SelectTrigger
                class="h-10 w-full text-sm"
                :aria-label="t('problemSets.list.visibility')"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="public">
                  {{ t('problemSets.list.visibilityPublic') }}
                </SelectItem>
                <SelectItem value="private">
                  {{ t('problemSets.list.visibilityPrivate') }}
                </SelectItem>
              </SelectContent>
            </Select>
            <p class="text-[13px] leading-5 text-muted-foreground">
              {{ t('problemSets.form.visibilityTip') }}
            </p>
          </div>
        </div>
      </section>

      <section>
        <div class="h-px bg-border" role="separator" />
        <h2 class="pt-8 text-lg font-medium">{{ t('problemSets.list.descLabel') }}</h2>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('problemSets.form.descHint') }}
        </p>
        <div class="my-5 h-px bg-border" role="separator" />
        <MarkdownEditor
          v-model="form.description"
          min-height="320px"
          :placeholder="t('problemSets.form.descPlaceholder')"
        />
      </section>

        <div class="flex flex-wrap justify-start gap-2 pt-2">
        <Button type="submit" :disabled="submitting || loading">
          <Loader2 v-if="submitting" class="size-4 animate-spin" />
          {{ isEdit ? t('action.save') : t('problemSets.form.createAction') }}
        </Button>
        <Button type="button" variant="outline" :disabled="submitting" @click="cancel">
          {{ t('action.cancel') }}
        </Button>
      </div>
    </form>
  </div>
</template>
