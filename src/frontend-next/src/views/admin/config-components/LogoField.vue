<script setup lang="ts">
/**
 * site.logo 编辑器：左侧预览 + 外链 URL 输入 + 站内 Logo 上传（存 MinIO site/logo/）。
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ImagePlus, Loader2 } from '@lucide/vue'

import { uploadSiteLogo } from '@/api/files'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { message } from '@/utils/feedback'
import { isRenderableLogo } from '@/utils/logo'

const model = defineModel<string>({ default: '' })
const { t } = useI18n()

const IMAGE_ACCEPT = 'image/jpeg,image/png,image/webp,image/gif'
const IMAGE_TYPES = IMAGE_ACCEPT.split(',')
const MAX_IMAGE_BYTES = 5 * 1024 * 1024

const fileInput = ref<HTMLInputElement>()
const uploading = ref(false)

/** 仅渲染可识别形态（外链 / 站内文件 URL），其余视为待填写 */
const preview = computed(() => (isRenderableLogo(model.value) ? model.value : ''))

async function onFileChange(event: Event): Promise<void> {
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
  uploading.value = true
  try {
    const result = await uploadSiteLogo(file)
    model.value = result.url
    message.success(t('common.success'))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.imageUploadFailed'))
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-4 sm:flex-row sm:items-start">
    <div
      class="grid size-24 shrink-0 place-items-center overflow-hidden rounded-lg border border-dashed border-border bg-surface"
    >
      <img v-if="preview" :src="preview" alt="" class="size-full object-contain" />
      <ImagePlus v-else class="size-6 text-muted-foreground" :stroke-width="1.5" />
    </div>

    <div class="min-w-0 flex-1 space-y-2.5">
      <Input
        :model-value="model"
        :placeholder="t('config.logoPlaceholder')"
        class="h-10 text-sm"
        @update:model-value="model = String($event)"
      />
      <div class="flex flex-wrap items-center gap-2.5">
        <Button variant="outline" size="sm" :disabled="uploading" @click="fileInput?.click()">
          <Loader2 v-if="uploading" class="size-4 animate-spin" />
          {{ t('config.uploadLogo') }}
        </Button>
        <span class="text-[13px] leading-5 text-muted-foreground">{{ t('config.logoHint') }}</span>
      </div>
      <input
        ref="fileInput"
        type="file"
        :accept="IMAGE_ACCEPT"
        class="hidden"
        @change="onFileChange"
      />
    </div>
  </div>
</template>
