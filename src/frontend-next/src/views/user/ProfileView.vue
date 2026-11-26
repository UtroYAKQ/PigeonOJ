<script setup lang="ts">
/**
 * 个人资料（/user/profile）：头像上传 / 昵称 / 签名 / 主题。
 * 主题选择即时联动 app store（html.dark + 本地持久化），保存时随资料写回用户偏好。
 */
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ImagePlus, Loader2, Moon, Sun } from '@lucide/vue'

import { uploadAvatar } from '@/api/files'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
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
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { EDITOR_FONT_OPTIONS, EDITOR_FONT_SIZES } from '@/constants/editorFonts'
import { useAppStore, type ThemeMode } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import UserSettingsShell from './components/UserSettingsShell.vue'

const { t } = useI18n()
const appStore = useAppStore()
const userStore = useUserStore()

const form = reactive({
  nickname: '',
  signature: '',
  avatar_url: '',
  theme: 'light' as ThemeMode,
  editor_font_size: 14,
  editor_font_family: 'jetbrains-mono',
})

const saving = ref(false)
const uploadingAvatar = ref(false)
const avatarInput = ref<HTMLInputElement>()

watch(
  () => userStore.user,
  (value) => {
    if (!value) return
    form.nickname = value.nickname ?? ''
    form.signature = value.signature ?? ''
    form.avatar_url = value.avatar_url ?? ''
    form.theme = value.theme === 'dark' ? 'dark' : 'light'
    form.editor_font_size = value.editor_font_size ?? 14
    form.editor_font_family = value.editor_font_family ?? 'jetbrains-mono'
  },
  { immediate: true },
)

const dirty = computed(() => {
  const value = userStore.user
  if (!value) return false
  return (
    form.nickname !== (value.nickname ?? '') ||
    form.signature !== (value.signature ?? '') ||
    form.avatar_url !== (value.avatar_url ?? '') ||
    form.theme !== (value.theme === 'dark' ? 'dark' : 'light') ||
    form.editor_font_size !== (value.editor_font_size ?? 14) ||
    form.editor_font_family !== (value.editor_font_family ?? 'jetbrains-mono')
  )
})

function onFontFamilyChange(value: unknown): void {
  form.editor_font_family = String(value)
}

function onFontSizeChange(value: unknown): void {
  form.editor_font_size = Number(value) || 14
}

function onThemeChange(value: unknown): void {
  const next: ThemeMode = String(value) === 'dark' ? 'dark' : 'light'
  form.theme = next
  // 即时预览：与顶栏主题切换共用 app store 的呈现与持久化逻辑
  appStore.setTheme(next)
}

async function onAvatarChosen(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const allowed = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
  if (!allowed.includes(file.type) || file.size > 2 * 1024 * 1024) {
    message.warning(t('profile.invalidAvatar'))
    return
  }
  uploadingAvatar.value = true
  try {
    const result = await uploadAvatar(file)
    form.avatar_url = result.url
    message.success(t('profile.uploadSuccess'))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('profile.uploadFailed'))
  } finally {
    uploadingAvatar.value = false
  }
}

async function onSave(): Promise<void> {
  if (!form.nickname.trim()) {
    message.warning(t('profile.nicknameRequired'))
    return
  }
  saving.value = true
  try {
    await userStore.updateProfile({
      nickname: form.nickname.trim(),
      signature: form.signature.trim() || null,
      avatar_url: form.avatar_url || null,
      theme: form.theme,
      editor_font_size: form.editor_font_size,
      editor_font_family: form.editor_font_family,
    })
    message.success(t('profile.saved'))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UserSettingsShell>
    <div class="grid gap-4 md:grid-cols-[minmax(0,280px)_minmax(0,1fr)] md:items-start">
      <section class="rounded-xl border border-border bg-card p-5">
        <div class="flex flex-col items-center text-center">
          <BaseAvatar :src="form.avatar_url || null" :name="form.nickname" :size="96" />
          <Button
            variant="outline"
            size="sm"
            class="mt-3 h-8"
            :disabled="uploadingAvatar"
            @click="avatarInput?.click()"
          >
            <Loader2 v-if="uploadingAvatar" class="size-3.5 animate-spin" />
            <ImagePlus v-else class="size-3.5" />
            {{ form.avatar_url ? t('action.change') : t('action.upload') }}
          </Button>
          <input
            ref="avatarInput"
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            class="hidden"
            @change="onAvatarChosen"
          />
          <p class="mt-3 truncate text-[15px] font-semibold">{{ form.nickname || '—' }}</p>
          <p class="w-full truncate text-[12.5px] text-muted-foreground">
            {{ userStore.user?.email }}
          </p>
        </div>

        <dl class="mt-5 space-y-3 border-t border-border pt-4">
          <div class="flex items-center justify-between gap-3">
            <dt class="shrink-0 text-[12px] text-muted-foreground">{{ t('profile.email') }}</dt>
            <dd class="flex min-w-0 items-center gap-1.5 text-[12.5px]">
              <span class="truncate">{{ userStore.user?.email }}</span>
              <ToneBadge
                v-if="userStore.user?.email_verified"
                tone="success"
                :label="t('profile.verified')"
              />
              <ToneBadge v-else tone="warning" :label="t('profile.unverified')" />
            </dd>
          </div>
          <div class="flex items-center justify-between gap-3">
            <dt class="shrink-0 text-[12px] text-muted-foreground">{{ t('profile.createdAt') }}</dt>
            <dd class="text-[12.5px] tabular-nums">
              {{ formatDateTime(userStore.user?.created_at) }}
            </dd>
          </div>
        </dl>
      </section>

      <section class="rounded-xl border border-border bg-card">
        <header
          class="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3.5"
        >
          <h2 class="text-[14px] font-semibold">{{ t('profile.title') }}</h2>
          <div class="flex items-center gap-2">
            <ToneBadge v-if="dirty" tone="warning" :label="t('profile.unsaved')" />
            <Button size="sm" class="h-8" :disabled="saving || !dirty" @click="onSave">
              <Loader2 v-if="saving" class="size-3.5 animate-spin" />
              {{ t('profile.saveChanges') }}
            </Button>
          </div>
        </header>

        <form class="space-y-4 px-5 py-4" @submit.prevent="onSave">
          <div class="grid gap-1.5">
            <div class="flex items-center justify-between">
              <Label for="profile-nickname" class="text-[12.5px]">{{ t('profile.nickname') }}</Label>
              <span class="text-[11px] tabular-nums text-muted-foreground">
                {{ form.nickname.length }}/64
              </span>
            </div>
            <Input
              id="profile-nickname"
              v-model="form.nickname"
              maxlength="64"
              class="h-9 text-[13px]"
            />
          </div>

          <div class="grid gap-1.5">
            <div class="flex items-center justify-between">
              <Label for="profile-signature" class="text-[12.5px]">
                {{ t('profile.signature') }}
              </Label>
              <span class="text-[11px] tabular-nums text-muted-foreground">
                {{ form.signature.length }}/255
              </span>
            </div>
            <Input
              id="profile-signature"
              v-model="form.signature"
              maxlength="255"
              :placeholder="t('profile.signatureHint')"
              class="h-9 text-[13px]"
            />
          </div>

          <div class="grid gap-1.5">
            <Label class="text-[12.5px]">{{ t('profile.theme') }}</Label>
            <Tabs :model-value="form.theme" @update:model-value="onThemeChange">
              <TabsList class="w-fit">
                <TabsTrigger value="light" class="gap-1.5 px-3 text-[12.5px]">
                  <Sun class="size-3.5" />
                  {{ t('profile.light') }}
                </TabsTrigger>
                <TabsTrigger value="dark" class="gap-1.5 px-3 text-[12.5px]">
                  <Moon class="size-3.5" />
                  {{ t('profile.dark') }}
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          <div class="grid gap-1.5">
            <Label class="text-[12.5px]">{{ t('profile.editorFontFamily') }}</Label>
            <Select :model-value="form.editor_font_family" @update:model-value="onFontFamilyChange">
              <SelectTrigger class="h-9 w-[220px] text-[13px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="option in EDITOR_FONT_OPTIONS" :key="option.value" :value="option.value">
                  {{ option.value === 'system' ? t('profile.fontSystem') : option.label }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div class="grid gap-1.5">
            <Label class="text-[12.5px]">{{ t('profile.editorFontSize') }}</Label>
            <Select :model-value="String(form.editor_font_size)" @update:model-value="onFontSizeChange">
              <SelectTrigger class="h-9 w-[110px] text-[13px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="size in EDITOR_FONT_SIZES" :key="size" :value="String(size)">
                  {{ size }} px
                </SelectItem>
              </SelectContent>
            </Select>
            <p class="text-[12px] leading-5 text-muted-foreground">
              {{ t('profile.editorFontHint') }}
            </p>
          </div>
        </form>
      </section>
    </div>
  </UserSettingsShell>
</template>
