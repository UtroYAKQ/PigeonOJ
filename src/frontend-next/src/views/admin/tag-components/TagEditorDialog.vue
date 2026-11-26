<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { adminCreateTag, adminUpdateTag } from '@/api/admin'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { message } from '@/utils/feedback'
import type { ProblemTagItem } from '@/types'

const props = defineProps<{
  open: boolean
  tag: ProblemTagItem | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  saved: []
}>()

const { t } = useI18n()
const formName = ref('')
const formColor = ref('')
const submitting = ref(false)

const isEdit = computed(() => Boolean(props.tag))

watch(
  () => props.open,
  (open) => {
    if (!open) return
    formName.value = props.tag?.name ?? ''
    formColor.value = props.tag?.color ?? ''
  },
)

function close(): void {
  emit('update:open', false)
}

function onPickColor(event: Event): void {
  formColor.value = (event.target as HTMLInputElement).value
}

async function submit(): Promise<void> {
  const name = formName.value.trim()
  if (!name || submitting.value) return
  submitting.value = true
  try {
    const color = formColor.value.trim() || null
    if (props.tag) {
      await adminUpdateTag(props.tag.id, { name, color })
      message.success(t('admin.tags.updated'))
    } else {
      await adminCreateTag({ name, color })
      message.success(t('admin.tags.created'))
    }
    close()
    emit('saved')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="sm:max-w-[420px]">
      <DialogHeader>
        <DialogTitle class="text-[15px] font-semibold">
          {{ isEdit ? t('admin.tags.edit') : t('admin.tags.create') }}
        </DialogTitle>
        <DialogDescription class="sr-only">{{ t('admin.tags.name') }}</DialogDescription>
      </DialogHeader>

      <form class="grid gap-4" @submit.prevent="submit">
        <div class="grid gap-1.5">
          <Label for="admin-tag-name" class="text-[13px]">{{ t('admin.tags.name') }}</Label>
          <Input
            id="admin-tag-name"
            v-model="formName"
            maxlength="32"
            class="h-9 text-[13px]"
            :placeholder="t('admin.tags.namePlaceholder')"
          />
          <p class="text-right text-[11px] tabular-nums text-muted-foreground">
            {{ formName.length }}/32
          </p>
        </div>

        <div class="grid gap-1.5">
          <Label for="admin-tag-color" class="text-[13px]">{{ t('admin.tags.color') }}</Label>
          <div class="flex items-center gap-2">
            <input
              type="color"
              class="h-9 w-11 shrink-0 cursor-pointer rounded-md border border-input bg-transparent p-1"
              :value="formColor || '#d9480f'"
              :aria-label="t('admin.tags.color')"
              @input="onPickColor"
            />
            <Input
              id="admin-tag-color"
              v-model="formColor"
              maxlength="7"
              class="h-9 font-mono text-[13px]"
              placeholder="#RRGGBB"
            />
          </div>
        </div>
      </form>

      <DialogFooter>
        <Button variant="outline" size="sm" :disabled="submitting" @click="close">
          {{ t('action.cancel') }}
        </Button>
        <Button size="sm" :disabled="!formName.trim() || submitting" @click="submit">
          <Loader2 v-if="submitting" class="size-4 animate-spin" />
          {{ t('action.save') }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
