<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, LogOut, Trash2 } from '@lucide/vue'

import { disbandTeam, exitTeam, updateTeam } from '@/api/teams'
import { uploadImage } from '@/api/files'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
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
import { Textarea } from '@/components/ui/textarea'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import type { TeamDetail, TeamVisibilityType } from '@/types'

const props = defineProps<{
  team: TeamDetail
  isAdmin: boolean
  isCreator: boolean
}>()

const emit = defineEmits<{
  updated: [team: TeamDetail]
  left: [kind: 'exit' | 'disband']
}>()

const { t } = useI18n()

const form = reactive({
  name: '',
  description: '',
  avatar_url: '',
  visibility: 'private' as TeamVisibilityType,
})
const saving = ref(false)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement>()

function reset(): void {
  form.name = props.team.name
  form.description = props.team.description ?? ''
  form.avatar_url = props.team.avatar_url ?? ''
  form.visibility = props.team.visibility ?? 'private'
}

function onVisibilityChange(value: unknown): void {
  form.visibility = value === 'public' ? 'public' : 'private'
}

watch(
  () => [props.team.name, props.team.description, props.team.avatar_url, props.team.visibility],
  reset,
  { immediate: true },
)

async function save(): Promise<void> {
  if (saving.value) return
  if (!form.name.trim()) {
    message.warning(t('teams.create.nameRequired'))
    return
  }
  saving.value = true
  try {
    const updated = await updateTeam(props.team.id, {
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      avatar_url: form.avatar_url || undefined,
      visibility: form.visibility,
    })
    emit('updated', updated)
    message.success(t('teams.settings.saved'))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    saving.value = false
  }
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

function onExit(): void {
  confirmAsyncDialog({
    title: t('teams.detail.exit'),
    content: t('teams.detail.exitConfirm'),
    positiveText: t('teams.detail.exit'),
    danger: true,
    action: () => exitTeam(props.team.id),
    successMessage: t('teams.detail.exitSuccess'),
    onAfterSuccess: () => emit('left', 'exit'),
  })
}

function onDisband(): void {
  confirmAsyncDialog({
    title: t('teams.detail.disband'),
    content: t('teams.detail.disbandConfirm'),
    positiveText: t('teams.detail.disband'),
    danger: true,
    action: () => disbandTeam(props.team.id),
    successMessage: t('teams.detail.disbandSuccess'),
    onAfterSuccess: () => emit('left', 'disband'),
  })
}
</script>

<template>
  <div class="min-h-0 flex-1 overflow-y-auto">
    <div class="mx-auto w-full max-w-[960px] pb-6">
      <!-- 与组织设置一致：标题 + 说明 + 分隔线 + 无边框表单 -->
      <h3 class="text-lg font-medium">{{ t('teams.settings.infoTitle') }}</h3>
      <p class="mt-1 text-sm text-muted-foreground">
        {{ t('teams.settings.infoDescription') }}
      </p>
      <div class="my-5 h-px bg-border" role="separator" />

      <form v-if="isAdmin" class="space-y-8" @submit.prevent="save">
        <div class="grid gap-2">
          <div class="flex items-center justify-between">
            <Label for="team-settings-name" class="text-sm font-medium">
              {{ t('teams.create.name') }}
              <span class="text-destructive">*</span>
            </Label>
            <span class="text-[11px] tabular-nums text-muted-foreground">
              {{ form.name.length }}/64
            </span>
          </div>
          <Input
            id="team-settings-name"
            v-model="form.name"
            :maxlength="64"
            :placeholder="t('teams.create.namePlaceholder')"
            class="h-10 text-sm"
          />
          <p class="text-[13px] leading-5 text-muted-foreground">
            {{ t('teams.settings.nameHint') }}
          </p>
        </div>

        <div class="grid gap-2">
          <Label for="team-settings-desc" class="text-sm font-medium">
            {{ t('teams.create.description') }}
          </Label>
          <Textarea
            id="team-settings-desc"
            v-model="form.description"
            :maxlength="2000"
            :placeholder="t('teams.create.descriptionPlaceholder')"
            class="min-h-[120px] text-sm"
          />
          <p class="text-[13px] leading-5 text-muted-foreground">
            {{ t('teams.settings.descriptionHint') }}
          </p>
        </div>

        <div class="grid gap-2">
          <Label class="text-sm font-medium">{{ t('teams.settings.visibility') }}</Label>
          <Select :model-value="form.visibility" @update:model-value="onVisibilityChange">
            <SelectTrigger class="h-10 w-full text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="private">{{ t('teams.settings.visibilityPrivate') }}</SelectItem>
              <SelectItem value="public">{{ t('teams.settings.visibilityPublic') }}</SelectItem>
            </SelectContent>
          </Select>
          <p class="text-[13px] leading-5 text-muted-foreground">
            {{ t('teams.settings.visibilityHint') }}
          </p>
        </div>

        <div class="grid gap-2">
          <Label class="text-sm font-medium">{{ t('teams.settings.avatar') }}</Label>
          <div class="flex flex-wrap items-center gap-4">
            <BaseAvatar
              kind="team"
              :src="form.avatar_url || null"
              :name="form.name"
              :size="64"
              :round="false"
              :radius="12"
              bordered
            />
            <Button variant="outline" :disabled="uploading" @click="fileInput?.click()">
              <Loader2 v-if="uploading" class="size-4 animate-spin" />
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
          <p class="text-[13px] leading-5 text-muted-foreground">
            {{ t('teams.settings.avatarHint') }}
          </p>
        </div>

        <div class="flex justify-start">
          <Button type="submit" :disabled="saving">
            <Loader2 v-if="saving" class="size-4 animate-spin" />
            {{ t('action.save') }}
          </Button>
        </div>
      </form>

      <!-- 普通成员只读摘要 -->
      <div v-else class="space-y-3">
        <p class="text-sm leading-6 text-muted-foreground">
          {{ team.description || t('teams.detail.descEmpty') }}
        </p>
        <p class="text-[13px] text-muted-foreground">
          {{ t('teams.list.memberCount') }}
          <strong class="ml-1 font-semibold tabular-nums text-foreground">
            {{ team.member_count }}
          </strong>
        </p>
      </div>

      <!-- 危险操作：创建者解散，其余成员退出 -->
      <div class="my-8 h-px bg-border" role="separator" />
      <section>
        <h3 class="text-lg font-medium">{{ t('teams.settings.dangerTitle') }}</h3>
        <p class="mt-1 max-w-[80ch] text-sm leading-5 text-muted-foreground">
          {{ isCreator ? t('teams.detail.disbandConfirm') : t('teams.detail.exitConfirm') }}
        </p>
        <Button variant="destructive" class="mt-4" @click="isCreator ? onDisband() : onExit()">
          <Trash2 v-if="isCreator" class="size-4" />
          <LogOut v-else class="size-4" />
          {{ isCreator ? t('teams.detail.disband') : t('teams.detail.exit') }}
        </Button>
      </section>
    </div>
  </div>
</template>
