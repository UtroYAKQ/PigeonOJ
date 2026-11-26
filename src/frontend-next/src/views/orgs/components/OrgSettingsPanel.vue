<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2, Upload } from '@lucide/vue'

import { uploadImage } from '@/api/files'
import { disbandOrg, updateOrg } from '@/api/orgs'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { confirmDialog, message } from '@/utils/feedback'
import type { OrgDetail } from '@/types'

const props = defineProps<{ org: OrgDetail; canManage: boolean; siteAdmin: boolean }>()
const emit = defineEmits<{ refresh: [] }>()

const router = useRouter()
const { t } = useI18n()

const form = reactive({ name: '', description: '', avatar_url: '' })
const saving = ref(false)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement>()

watch(
  () => props.org,
  (org) => {
    form.name = org.name
    form.description = org.description ?? ''
    form.avatar_url = org.avatar_url ?? ''
  },
  { immediate: true },
)

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
    form.avatar_url = (await uploadImage(file)).url
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.imageUploadFailed'))
  } finally {
    uploading.value = false
  }
}

async function save(): Promise<void> {
  if (!form.name.trim()) {
    message.warning(t('orgs.create.nameRequired'))
    return
  }
  saving.value = true
  try {
    await updateOrg(props.org.id, {
      name: form.name.trim(),
      description: form.description.trim(),
      avatar_url: form.avatar_url.trim(),
    })
    message.success(t('orgs.settings.saved'))
    emit('refresh')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    saving.value = false
  }
}

async function disband(): Promise<void> {
  const ok = await confirmDialog({
    title: t('orgs.settings.disband'),
    content: t('orgs.settings.disbandConfirm'),
    positiveText: t('orgs.settings.disband'),
    negativeText: t('action.cancel'),
    danger: true,
  })
  if (!ok) return
  try {
    await disbandOrg(props.org.id)
    message.success(t('orgs.settings.disbandSuccess'))
    void router.push('/admin/orgs')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}
</script>

<template>
  <div class="min-h-0 flex-1 overflow-y-auto">
    <div class="mx-auto w-full max-w-[960px] pb-6">
      <!-- shadcn-vue-admin 设置页版式：标题 + 说明 + 分隔线 + 无边框表单 -->
      <h3 class="text-lg font-medium">{{ t('orgs.settings.infoTitle') }}</h3>
      <p class="mt-1 text-sm text-muted-foreground">
        {{ t('orgs.settings.infoDescription') }}
      </p>
      <div class="my-5 h-px bg-border" role="separator" />

      <form class="space-y-8" @submit.prevent="save">
        <div class="grid gap-2">
          <Label for="org-name" class="text-sm font-medium">
            {{ t('orgs.create.name') }}
            <span class="text-destructive" aria-hidden="true">*</span>
          </Label>
          <Input id="org-name" v-model="form.name" maxlength="64" class="h-10 text-sm" />
          <p class="text-[13px] leading-5 text-muted-foreground">
            {{ t('orgs.settings.nameHint') }}
          </p>
        </div>

        <div class="grid gap-2">
          <Label for="org-desc" class="text-sm font-medium">
            {{ t('orgs.create.description') }}
          </Label>
          <Textarea
            id="org-desc"
            v-model="form.description"
            rows="5"
            maxlength="2000"
            class="min-h-[120px] text-sm"
            :placeholder="t('orgs.create.descriptionPlaceholder')"
          />
          <p class="text-[13px] leading-5 text-muted-foreground">
            {{ t('orgs.settings.descriptionHint') }}
          </p>
        </div>

        <div class="grid gap-2">
          <Label class="text-sm font-medium">{{ t('orgs.settings.avatar') }}</Label>
          <div class="flex flex-wrap items-center gap-4">
            <BaseAvatar
              :src="form.avatar_url || null"
              :name="form.name"
              kind="team"
              :size="64"
              :round="false"
              :radius="12"
              bordered
            />
            <Button
              type="button"
              variant="outline"
              :disabled="uploading || !canManage"
              @click="fileInput?.click()"
            >
              <Loader2 v-if="uploading" class="size-4 animate-spin" />
              <Upload v-else class="size-4" />
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
            {{ t('orgs.settings.avatarHint') }}
          </p>
        </div>

        <div v-if="canManage" class="flex justify-start">
          <Button type="submit" :disabled="saving">
            <Loader2 v-if="saving" class="size-4 animate-spin" />
            {{ t('action.save') }}
          </Button>
        </div>
      </form>

      <template v-if="siteAdmin">
        <div class="my-8 h-px bg-border" role="separator" />
        <section>
          <h3 class="text-lg font-medium">{{ t('orgs.settings.disband') }}</h3>
          <p class="mt-1 max-w-[80ch] text-sm leading-5 text-muted-foreground">
            {{ t('orgs.settings.disbandConfirm') }}
          </p>
          <Button variant="destructive" class="mt-4" @click="disband">
            {{ t('orgs.settings.disband') }}
          </Button>
        </section>
      </template>
    </div>
  </div>
</template>
