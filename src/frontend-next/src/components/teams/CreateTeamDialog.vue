<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { uploadImage } from '@/api/files'
import { createOrgTeam } from '@/api/orgs'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { message } from '@/utils/feedback'
import type { TeamSummary, TeamVisibilityType } from '@/types'

const props = defineProps<{ open: boolean; orgId: string }>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  created: [team: TeamSummary]
}>()

const { t } = useI18n()

const form = reactive({
  name: '',
  description: '',
  avatar_url: '',
  visibility: 'private' as TeamVisibilityType,
})
const submitting = ref(false)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement>()

watch(
  () => props.open,
  (open) => {
    if (!open) return
    form.name = ''
    form.description = ''
    form.avatar_url = ''
    form.visibility = 'private'
    submitting.value = false
    uploading.value = false
  },
)

function close(): void {
  if (submitting.value) return
  emit('update:open', false)
}

function onOpenChange(value: boolean): void {
  if (submitting.value) return
  emit('update:open', value)
}

function onVisibilityChange(value: unknown): void {
  form.visibility = value === 'public' ? 'public' : 'private'
}

const IMAGE_ACCEPT = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
const MAX_IMAGE_BYTES = 5 * 1024 * 1024

async function onAvatarChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!IMAGE_ACCEPT.includes(file.type)) {
    message.error(t('common.imageTypeInvalid'))
    return
  }
  if (file.size > MAX_IMAGE_BYTES) {
    message.error(t('common.imageTooLarge'))
    return
  }
  uploading.value = true
  try {
    const result = await uploadImage(file)
    form.avatar_url = result.url
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.imageUploadFailed'))
  } finally {
    uploading.value = false
  }
}

async function submit(): Promise<void> {
  if (submitting.value) return
  if (!form.name.trim()) {
    message.warning(t('teams.create.nameRequired'))
    return
  }
  submitting.value = true
  try {
    const team = await createOrgTeam(props.orgId, {
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      avatar_url: form.avatar_url || undefined,
      visibility: form.visibility,
    })
    message.success(t('teams.create.success'))
    emit('created', team)
    close()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="onOpenChange">
    <DialogContent class="sm:max-w-[520px]">
      <DialogHeader>
        <DialogTitle>{{ t('orgs.teams.createTitle') }}</DialogTitle>
        <DialogDescription class="sr-only">{{ t('teams.create.name') }}</DialogDescription>
      </DialogHeader>

      <form class="grid gap-4" @submit.prevent="submit">
        <div class="grid gap-1.5">
          <Label for="create-team-name" class="text-[13px]">
            {{ t('teams.create.name') }}
            <span class="text-destructive">*</span>
          </Label>
          <Input
            id="create-team-name"
            v-model="form.name"
            :maxlength="64"
            :placeholder="t('teams.create.namePlaceholder')"
            class="h-9 text-[13px]"
          />
        </div>

        <div class="grid gap-1.5">
          <Label for="create-team-desc" class="text-[13px]">
            {{ t('teams.create.description') }}
          </Label>
          <Textarea
            id="create-team-desc"
            v-model="form.description"
            :maxlength="2000"
            :placeholder="t('teams.create.descriptionPlaceholder')"
            class="min-h-[84px] text-[13px]"
          />
        </div>

        <div class="grid gap-1.5">
          <Label class="text-[13px]">{{ t('teams.settings.visibility') }}</Label>
          <Select :model-value="form.visibility" @update:model-value="onVisibilityChange">
            <SelectTrigger class="h-9 w-full text-[13px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="private">{{ t('teams.settings.visibilityPrivate') }}</SelectItem>
              <SelectItem value="public">{{ t('teams.settings.visibilityPublic') }}</SelectItem>
            </SelectContent>
          </Select>
          <p class="text-[12px] leading-5 text-muted-foreground">
            {{ t('teams.settings.visibilityHint') }}
          </p>
        </div>

        <div class="grid gap-1.5">
          <Label class="text-[13px]">{{ t('teams.settings.avatar') }}</Label>
          <div class="flex flex-wrap items-center gap-3">
            <BaseAvatar
              kind="team"
              :src="form.avatar_url || null"
              :name="form.name"
              :size="44"
              :round="false"
              :radius="10"
              bordered
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              :disabled="uploading"
              @click="fileInput?.click()"
            >
              <Loader2 v-if="uploading" class="size-3.5 animate-spin" />
              {{ t('action.upload') }}
            </Button>
            <input
              ref="fileInput"
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              class="hidden"
              @change="onAvatarChange"
            />
          </div>
        </div>
      </form>

      <DialogFooter>
        <Button variant="outline" size="sm" :disabled="submitting" @click="close">
          {{ t('action.cancel') }}
        </Button>
        <Button size="sm" :disabled="submitting || uploading" @click="submit">
          <Loader2 v-if="submitting" class="size-3.5 animate-spin" />
          {{ t('action.save') }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
