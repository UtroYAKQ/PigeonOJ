<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, Loader2 } from '@lucide/vue'

import { createSolution, getSolution, updateSolution } from '@/api/community'
import InlineNotice from '@/components/common/InlineNotice.vue'
import MarkdownEditor from '@/components/common/MarkdownEditor.vue'
import PageShell from '@/components/common/PageShell.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'
import { useSolutionContext } from './useSolutionContext'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()
const { problemId, solutionsBase } = useSolutionContext()

const solutionId = route.params.solutionId ? String(route.params.solutionId) : null
const isEdit = computed(() => solutionId !== null)
const loading = ref(false)
const saving = ref(false)
const removed = ref(false)
const form = reactive({ title: '', content: '' })

async function loadExisting(): Promise<void> {
  if (!solutionId) return
  loading.value = true
  try {
    const solution = await getSolution(solutionId)
    if (solution.author.id !== userStore.user?.id && !userStore.isAdmin) {
      message.error(t('problems.solutions.notOwner'))
      void router.replace(solutionsBase.value)
      return
    }
    form.title = solution.title
    form.content = solution.content
    removed.value = solution.status === 'removed'
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
    void router.replace(solutionsBase.value)
  } finally {
    loading.value = false
  }
}

async function submit(): Promise<void> {
  if (!form.title.trim()) {
    message.warning(t('problems.solutions.titleRequired'))
    return
  }
  if (!form.content.trim()) {
    message.warning(t('problems.solutions.contentRequired'))
    return
  }
  if (removed.value) {
    message.warning(t('problems.solutions.removedLocked'))
    return
  }
  saving.value = true
  try {
    const payload = { title: form.title.trim(), content: form.content }
    const solution = isEdit.value && solutionId
      ? await updateSolution(solutionId, payload)
      : await createSolution(problemId.value, payload)
    message.success(t('common.success'))
    void router.replace(`${solutionsBase.value}/${solution.id}`)
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
        {{ isEdit ? t('problems.solutions.editTitle') : t('problems.solutions.createTitle') }}
      </h1>
    </template>
    <template #actions>
      <Button variant="outline" size="sm" @click="router.push(solutionsBase)">
        <ArrowLeft class="size-4" />
        {{ t('problems.solutions.backToList') }}
      </Button>
      <Button size="sm" :disabled="saving || loading || removed" @click="submit">
        <Loader2 v-if="saving" class="size-4 animate-spin" />
        {{ t('problems.solutions.publish') }}
      </Button>
    </template>

    <div v-if="loading" class="grid h-40 place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else class="grid gap-4">
      <InlineNotice v-if="removed" tone="warning">
        {{ t('problems.solutions.removedLocked') }}
      </InlineNotice>
      <div class="grid gap-1.5">
        <Label for="solution-title" class="text-[13px]">
          {{ t('problems.solutions.titleLabel') }}
          <span class="text-destructive" aria-hidden="true">*</span>
        </Label>
        <Input
          id="solution-title"
          v-model="form.title"
          maxlength="255"
          class="h-9 text-[13px]"
          :placeholder="t('problems.solutions.titlePlaceholder')"
        />
      </div>
      <div class="grid gap-1.5">
        <Label class="text-[13px]">{{ t('problems.solutions.contentLabel') }}</Label>
        <MarkdownEditor
          v-model="form.content"
          min-height="480px"
          :placeholder="t('problems.solutions.contentPlaceholder')"
        />
      </div>
    </div>
  </PageShell>
</template>