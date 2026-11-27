<script setup lang="ts">
/**
 * 首页轮播海报列表编辑器（site.banners）：
 * 图片上传（公共图片接口）+ 标题 + 跳转路径，支持增删与上下移动排序，最多 10 张。
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowDown, ArrowUp, ImagePlus, Loader2, Plus, Trash2 } from '@lucide/vue'

import { uploadImage } from '@/api/files'
import LineList from '@/components/common/LineList.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { message } from '@/utils/feedback'
import { MAX_BANNERS, type BannerDraft } from './banners'

const props = withDefaults(defineProps<{ max?: number }>(), { max: MAX_BANNERS })

const banner = defineModel<BannerDraft[]>({ default: () => [] })
const { t } = useI18n()

const IMAGE_ACCEPT = 'image/jpeg,image/png,image/webp,image/gif'
const IMAGE_TYPES = IMAGE_ACCEPT.split(',')
const MAX_IMAGE_BYTES = 5 * 1024 * 1024

const fileInput = ref<HTMLInputElement>()
const uploadIndex = ref<number | null>(null)
const uploading = ref(false)

function patch(index: number, field: keyof BannerDraft, next: string): void {
  banner.value = banner.value.map((item, current) =>
    current === index ? { ...item, [field]: next } : item,
  )
}

function add(): void {
  if (banner.value.length >= props.max) {
    message.warning(t('config.bannersMax'))
    return
  }
  banner.value = [...banner.value, { image: '', title: '', link: '' }]
}

function remove(index: number): void {
  banner.value = banner.value.filter((_, current) => current !== index)
}

function move(index: number, delta: number): void {
  const target = index + delta
  if (target < 0 || target >= banner.value.length) return
  const next = [...banner.value]
  const [moved] = next.splice(index, 1)
  next.splice(target, 0, moved as BannerDraft)
  banner.value = next
}

function pickImage(index: number): void {
  uploadIndex.value = index
  fileInput.value?.click()
}

async function onFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  const index = uploadIndex.value
  if (!file || index === null || !banner.value[index]) return
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
    const result = await uploadImage(file)
    patch(index, 'image', result.url)
    message.success(t('common.success'))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.imageUploadFailed'))
  } finally {
    uploading.value = false
    uploadIndex.value = null
  }
}
</script>

<template>
  <div class="space-y-4">
    <LineList :items="banner" :empty-text="t('config.bannersEmpty')">
      <template #item="{ item, index }">
        <div class="flex flex-wrap items-start gap-4 py-4 sm:flex-nowrap">
          <span
            class="mt-2 grid size-5 shrink-0 place-items-center rounded-full bg-muted text-[11px] font-semibold text-muted-foreground tabular-nums"
          >
            {{ index + 1 }}
          </span>

          <button
            type="button"
            class="relative grid aspect-video w-[132px] shrink-0 place-items-center overflow-hidden rounded-md border border-dashed border-border bg-surface text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground"
            :disabled="uploading && uploadIndex === index"
            :aria-label="item.image ? t('config.changeImage') : t('config.uploadImage')"
            @click="pickImage(index)"
          >
            <img
              v-if="item.image"
              :src="item.image"
              alt=""
              class="absolute inset-0 size-full object-cover"
              decoding="async"
            />
            <span v-else class="flex flex-col items-center gap-1 text-[11px]">
              <ImagePlus class="size-4" :stroke-width="1.6" />
              {{ t('config.uploadImage') }}
            </span>
            <span
              v-if="uploading && uploadIndex === index"
              class="absolute inset-0 grid place-items-center bg-black/45 text-white"
            >
              <Loader2 class="size-4 animate-spin" />
            </span>
          </button>

          <div class="grid min-w-0 flex-1 gap-3 sm:grid-cols-2">
            <Input
              :model-value="item.title"
              maxlength="60"
              :placeholder="t('config.bannerTitle')"
              class="h-10 text-sm"
              @update:model-value="patch(index, 'title', String($event))"
            />
            <Input
              :model-value="item.link"
              maxlength="255"
              :placeholder="t('config.bannerLink')"
              class="h-10 font-mono text-[13px]"
              @update:model-value="patch(index, 'link', String($event))"
            />
          </div>

          <div class="flex shrink-0 items-center gap-0.5 self-start">
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              class="size-8"
              :disabled="index === 0"
              :aria-label="`${t('problemSets.detail.orderLabel')} ↑`"
              :title="`${t('problemSets.detail.orderLabel')} ↑`"
              @click="move(index, -1)"
            >
              <ArrowUp class="size-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              class="size-8"
              :disabled="index === banner.length - 1"
              :aria-label="`${t('problemSets.detail.orderLabel')} ↓`"
              :title="`${t('problemSets.detail.orderLabel')} ↓`"
              @click="move(index, 1)"
            >
              <ArrowDown class="size-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              class="size-8 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
              :aria-label="t('config.removeBanner')"
              :title="t('config.removeBanner')"
              @click="remove(index)"
            >
              <Trash2 class="size-4" />
            </Button>
          </div>
        </div>
      </template>
    </LineList>

    <Button type="button" variant="outline" :disabled="banner.length >= max" @click="add">
      <Plus class="size-4" />
      {{ t('config.addBanner') }}
    </Button>

    <input
      ref="fileInput"
      type="file"
      :accept="IMAGE_ACCEPT"
      class="hidden"
      @change="onFileChange"
    />
  </div>
</template>
