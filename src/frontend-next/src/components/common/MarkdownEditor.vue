<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Bold,
  Code,
  Code2,
  Eye,
  Heading2,
  ImagePlus,
  Italic,
  Link as LinkIcon,
  List,
  ListOrdered,
  Pencil,
  Quote,
  Sigma,
} from '@lucide/vue'

import MarkdownView from '@/components/common/MarkdownView.vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { uploadImage } from '@/api/files'
import { message } from '@/utils/feedback'

const props = withDefaults(
  defineProps<{
    modelValue: string
    placeholder?: string
    minHeight?: string
    compact?: boolean
  }>(),
  { placeholder: '', minHeight: '240px', compact: false },
)

const emit = defineEmits<{ 'update:modelValue': [string] }>()
const { t } = useI18n()

const tab = ref<'write' | 'preview'>('write')
const textarea = ref<HTMLTextAreaElement>()
const fileInput = ref<HTMLInputElement>()

const value = computed(() => props.modelValue ?? '')

const IMAGE_ACCEPT = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
const MAX_IMAGE_BYTES = 5 * 1024 * 1024

function commit(next: string, selectStart?: number, selectEnd?: number): void {
  emit('update:modelValue', next)
  if (selectStart === undefined) return
  void nextTick(() => {
    const el = textarea.value
    if (!el) return
    el.focus()
    el.setSelectionRange(selectStart, selectEnd ?? selectStart)
  })
}

function surround(before: string, after = before, fallback = ''): void {
  const el = textarea.value
  const text = value.value
  const start = el?.selectionStart ?? text.length
  const end = el?.selectionEnd ?? text.length
  const selected = text.slice(start, end) || fallback
  const next = text.slice(0, start) + before + selected + after + text.slice(end)
  commit(next, start + before.length, start + before.length + selected.length)
}

function prefixLines(prefix: string): void {
  const el = textarea.value
  const text = value.value
  const start = el?.selectionStart ?? text.length
  const end = el?.selectionEnd ?? text.length
  const lineStart = text.lastIndexOf('\n', start - 1) + 1
  const block = text.slice(lineStart, end)
  const nextBlock = block
    .split('\n')
    .map((line) => `${prefix}${line}`)
    .join('\n')
  const next = text.slice(0, lineStart) + nextBlock + text.slice(end)
  commit(next, lineStart, lineStart + nextBlock.length)
}

function insertImageMarkup(name: string, url: string): void {
  surround(`![${name}](${url})`, '', name || 'image')
}

async function uploadFiles(files: File[]): Promise<void> {
  const valid = files.filter((file) => IMAGE_ACCEPT.includes(file.type))
  if (!valid.length) {
    message.error(t('common.imageTypeInvalid'))
    return
  }
  const tip = message.loading(t('common.imageUploading'))
  try {
    for (const file of valid) {
      if (file.size > MAX_IMAGE_BYTES) {
        message.error(t('common.imageTooLarge'))
        continue
      }
      try {
        const result = await uploadImage(file)
        insertImageMarkup(file.name, result.url)
      } catch (error) {
        message.error(error instanceof Error ? error.message : t('common.imageUploadFailed'))
      }
    }
  } finally {
    tip.destroy()
  }
}

function pickImage(): void {
  fileInput.value?.click()
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  void uploadFiles(files)
}

function onPaste(event: ClipboardEvent): void {
  const files = Array.from(event.clipboardData?.files ?? [])
  if (!files.length) return
  event.preventDefault()
  void uploadFiles(files)
}

function withSelectionLink(): void {
  surround('[', '](https://)', t('editor.linkText'))
}
</script>

<template>
  <Card class="overflow-hidden">
    <div class="flex flex-wrap items-center gap-0.5 border-b border-border bg-muted/40 p-1">
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        :aria-label="t('editor.bold')"
        @click="surround('**', '**', t('editor.bold'))"
      >
        <Bold class="size-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        :aria-label="t('editor.italic')"
        @click="surround('*', '*', t('editor.italic'))"
      >
        <Italic class="size-3.5" />
      </Button>
      <Button
        v-if="!compact"
        type="button"
        variant="ghost"
        size="icon-xs"
        :aria-label="t('editor.heading')"
        @click="prefixLines('## ')"
      >
        <Heading2 class="size-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        :aria-label="t('editor.quote')"
        @click="prefixLines('> ')"
      >
        <Quote class="size-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        :aria-label="t('editor.unorderedList')"
        @click="prefixLines('- ')"
      >
        <List class="size-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        :aria-label="t('editor.orderedList')"
        @click="prefixLines('1. ')"
      >
        <ListOrdered class="size-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        :aria-label="t('editor.inlineCode')"
        @click="surround('`', '`', 'code')"
      >
        <Code class="size-3.5" />
      </Button>
      <Button
        v-if="!compact"
        type="button"
        variant="ghost"
        size="icon-xs"
        :aria-label="t('editor.codeBlock')"
        @click="surround('\n```\n', '\n```\n', 'code')"
      >
        <Code2 class="size-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        :aria-label="t('editor.link')"
        @click="withSelectionLink"
      >
        <LinkIcon class="size-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        :aria-label="t('editor.image')"
        @click="pickImage"
      >
        <ImagePlus class="size-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        :aria-label="t('editor.formula')"
        @click="surround('$', '$', 'x^2')"
      >
        <Sigma class="size-3.5" />
      </Button>

      <div class="ml-auto flex items-center gap-0.5">
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          :aria-label="tab === 'write' ? t('editor.preview') : t('editor.edit')"
          @click="tab = tab === 'write' ? 'preview' : 'write'"
        >
          <Eye v-if="tab === 'write'" class="size-3.5" />
          <Pencil v-else class="size-3.5" />
        </Button>
      </div>
    </div>

    <textarea
      v-show="tab === 'write'"
      ref="textarea"
      :value="value"
      :placeholder="placeholder"
      :style="{ minHeight }"
      class="block w-full resize-y border-0 bg-transparent p-3 font-mono text-[13px] leading-6 outline-none placeholder:text-muted-foreground"
      @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
      @paste="onPaste"
    />
    <div v-show="tab === 'preview'" :style="{ minHeight }" class="overflow-auto p-4">
      <MarkdownView v-if="value" :source="value" />
      <p v-else class="text-sm text-muted-foreground">{{ placeholder || t('editor.empty') }}</p>
    </div>

    <input
      ref="fileInput"
      type="file"
      accept="image/jpeg,image/png,image/webp,image/gif"
      class="hidden"
      @change="onFileChange"
    />
  </Card>
</template>
