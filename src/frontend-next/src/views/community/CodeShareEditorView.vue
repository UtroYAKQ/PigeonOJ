<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { createCodeShare, getCodeShare, updateCodeShare } from '@/api/community'
import CodeEditor from '@/components/common/CodeEditor.vue'
import InlineNotice from '@/components/common/InlineNotice.vue'
import PageShell from '@/components/common/PageShell.vue'
import LanguageSelect from '@/components/common/LanguageSelect.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'
import type { ProblemLanguage } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const shareId = route.params.id ? String(route.params.id) : null
const isEdit = computed(() => shareId !== null)
const loading = ref(false)
const saving = ref(false)
const removed = ref(false)
const form = reactive({
  title: '',
  language: 'cpp17' as ProblemLanguage,
  description: '',
  code: '',
})

async function loadExisting(): Promise<void> {
  if (!shareId) return
  loading.value = true
  try {
    const share = await getCodeShare(shareId)
    if (share.author.id !== userStore.user?.id) {
      message.error(t('codes.notOwner'))
      void router.replace('/codes')
      return
    }
    form.title = share.title
    form.language = share.language
    form.description = share.description ?? ''
    form.code = share.code
    removed.value = share.status === 'removed'
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
    void router.replace('/codes')
  } finally {
    loading.value = false
  }
}

async function submit(): Promise<void> {
  if (!form.title.trim()) {
    message.warning(t('codes.titleRequired'))
    return
  }
  if (!form.code.trim()) {
    message.warning(t('codes.codeRequired'))
    return
  }
  if (removed.value) {
    message.warning(t('codes.removedLocked'))
    return
  }
  saving.value = true
  try {
    const payload = {
      title: form.title.trim(),
      language: form.language,
      code: form.code,
      description: form.description.trim(),
    }
    const share =
      isEdit.value && shareId
        ? await updateCodeShare(shareId, payload)
        : await createCodeShare({ ...payload, description: payload.description || undefined })
    message.success(t('common.success'))
    void router.replace(`/codes/${share.id}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    saving.value = false
  }
}

onMounted(loadExisting)
</script>

<template>
  <PageShell width="narrow">
    <template #title>
      <h1 class="text-xl font-semibold leading-tight tracking-tight">
        {{ isEdit ? t('codes.editTitle') : t('codes.createTitle') }}
      </h1>
    </template>
    <template #actions>
      <Button size="sm" :disabled="saving || loading || removed" @click="submit">
        <Loader2 v-if="saving" class="size-4 animate-spin" />
        {{ isEdit ? t('codes.save') : t('codes.publish') }}
      </Button>
    </template>

    <div v-if="loading" class="grid h-40 place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else class="grid gap-4">
      <InlineNotice v-if="removed" tone="warning">
        {{ t('codes.removedLocked') }}
      </InlineNotice>

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