<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, Loader2 } from '@lucide/vue'

import { createCodeShare } from '@/api/community'
import CodeEditor from '@/components/common/CodeEditor.vue'
import MarkdownEditor from '@/components/common/MarkdownEditor.vue'
import PageShell from '@/components/common/PageShell.vue'
import LanguageSelect from '@/components/common/LanguageSelect.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { message } from '@/utils/feedback'
import type { ProblemLanguage } from '@/types'

const router = useRouter()
const { t } = useI18n()

const saving = ref(false)
const form = reactive({
  title: '',
  language: 'cpp17' as ProblemLanguage,
  description: '',
  code: '',
})

async function submit(): Promise<void> {
  if (!form.title.trim()) {
    message.warning(t('codes.titleRequired'))
    return
  }
  if (!form.code.trim()) {
    message.warning(t('codes.codeRequired'))
    return
  }
  saving.value = true
  try {
    const share = await createCodeShare({
      title: form.title.trim(),
      language: form.language,
      code: form.code,
      description: form.description.trim() || undefined,
    })
    message.success(t('common.success'))
    void router.replace(`/codes/${share.id}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <PageShell width="narrow">
    <template #title>
      <h1 class="text-xl font-semibold leading-tight tracking-tight">{{ t('codes.createTitle') }}</h1>
    </template>
    <template #actions>
      <Button variant="outline" size="sm" @click="router.push('/codes')">
        <ArrowLeft class="size-4" />
        {{ t('codes.backToList') }}
      </Button>
      <Button size="sm" :disabled="saving" @click="submit">
        <Loader2 v-if="saving" class="size-4 animate-spin" />
        {{ t('codes.publish') }}
      </Button>
    </template>

    <div class="grid gap-4">
      <div class="grid gap-1.5">
        <Label for="code-title" class="text-[13px]">
          {{ t('codes.titleLabel') }}
          <span class="text-destructive" aria-hidden="true">*</span>
        </Label>
        <Input
          id="code-title"
          v-model="form.title"
          maxlength="255"
          class="h-9 text-[13px]"
          :placeholder="t('codes.titlePlaceholder')"
        />
      </div>

      <div class="grid gap-1.5">
        <Label class="text-[13px]">{{ t('codes.languageLabel') }}</Label>
        <LanguageSelect v-model="form.language" class="w-[180px]" />
      </div>

      <div class="grid gap-1.5">
        <Label class="text-[13px]">{{ t('codes.descriptionLabel') }}</Label>
        <MarkdownEditor
          v-model="form.description"
          min-height="180px"
          :placeholder="t('codes.descriptionPlaceholder')"
        />
      </div>

      <div class="grid gap-1.5">
        <Label class="text-[13px]">
          {{ t('codes.codeLabel') }}
          <span class="text-destructive" aria-hidden="true">*</span>
        </Label>
        <div class="h-[360px]">
          <CodeEditor v-model="form.code" :language="form.language" />
        </div>
      </div>
    </div>
  </PageShell>
</template>