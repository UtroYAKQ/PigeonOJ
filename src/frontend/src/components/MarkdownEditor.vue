<script setup lang="ts">
/**
 * Markdown 编辑器（md-editor-v3 封装）：
 * CodeMirror 编辑 + 整块纯预览切换（非分屏）；支持 KaTeX 公式（本地实例，无 CDN 依赖）。
 * 存储仍为纯 Markdown 文本（契约 docs/contracts/problems.md），
 * 展示侧继续走 MarkdownView 渲染链路。深色模式与界面语言跟随全局设置（props 响应式）。
 */
import { computed } from 'vue'
import { MdEditor, config } from 'md-editor-v3'
import type { ToolbarNames } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { useI18n } from 'vue-i18n'
import { useAppStore } from '@/stores/app'
import { uploadImage } from '@/api/files'
import { message } from '@/utils/feedback'

// KaTeX 本地实例：公式渲染不依赖运行时 CDN（与展示侧 MarkdownView 能力对齐）
config({ editorExtensions: { katex: { instance: katex } } })

const props = withDefaults(
  defineProps<{
    modelValue: string
    placeholder?: string
    /** 编辑器高度（含工具栏），默认适配向导表单行 */
    minHeight?: string
    /** 窄容器精简模式：去掉表格 / 撤销重做等次要项，保证一行放下 */
    compact?: boolean
  }>(),
  { placeholder: '', minHeight: '220px', compact: false },
)
const emit = defineEmits<{ 'update:modelValue': [string] }>()

const appStore = useAppStore()
const { t, locale } = useI18n()

const value = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

/** 图片上传约束（与后端 FileService 口径一致） */
const IMAGE_ACCEPT = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
const MAX_IMAGE_BYTES = 5 * 1024 * 1024

// 完整工具栏：题面常用排版（宽容器）；'=' 后为纯预览切换（整块展示渲染结果，非左右分屏）
const fullToolbars: ToolbarNames[] = [
  'bold',
  'italic',
  'title',
  'quote',
  'unorderedList',
  'orderedList',
  '-',
  'codeRow',
  'code',
  'table',
  'link',
  'image',
  'katex',
  '-',
  'revoke',
  'next',
  '=',
  'previewOnly',
]
// 精简工具栏：半栏窄容器用；公式（OJ 约束常用）替代标题下拉，插图仍可粘贴 / 拖拽触发
const compactToolbars: ToolbarNames[] = [
  'bold',
  'italic',
  'title',
  'quote',
  'unorderedList',
  'orderedList',
  '-',
  'codeRow',
  'code',
  'link',
  'image',
  'katex',
  '=',
  'previewOnly',
]

/**
 * 公共图片上传：工具栏按钮 / 粘贴截图 / 拖拽图片均走 POST /files/upload/image，
 * 全部成功后回调插入 Markdown 引用；失败项逐条提示，成功项正常插入。
 */
async function handleUploadImg(
  files: File[],
  callback: (urls: Array<{ url: string; alt: string; title: string }>) => void,
) {
  const valid = files.filter((file) => IMAGE_ACCEPT.includes(file.type))
  if (valid.length === 0) {
    message.error(t('app.common.imageTypeInvalid'))
    return
  }
  const tip = message.loading(t('app.common.imageUploading'), { duration: 0 })
  const urls: Array<{ url: string; alt: string; title: string }> = []
  try {
    for (const file of valid) {
      if (file.size > MAX_IMAGE_BYTES) {
        message.error(t('app.common.imageTooLarge'))
        continue
      }
      try {
        const result = await uploadImage(file)
        urls.push({ url: result.url, alt: file.name, title: file.name })
      } catch (error) {
        message.error(error instanceof Error ? error.message : t('app.common.imageUploadFailed'))
      }
    }
  } finally {
    tip.destroy()
  }
  if (urls.length > 0) callback(urls)
}
</script>

<template>
  <!-- :key 跟随语言：切换语言时重建实例，确保编辑器 UI（工具栏提示等）立即切换；
       内容由 v-model 承载，重建不丢文本。语言偏好本身持久化于 localStorage（pigeonoj.locale） -->
  <MdEditor
    :key="locale"
    v-model="value"
    class="md-editor-shell"
    :theme="appStore.isDark ? 'dark' : 'light'"
    :language="locale === 'en-US' ? 'en-US' : 'zh-CN'"
    :height="minHeight"
    :placeholder="placeholder"
    :toolbars="compact ? compactToolbars : fullToolbars"
    :footers="[]"
    :preview="false"
    no-prettier
    no-mermaid
    @on-upload-img="handleUploadImg"
  />
</template>

<style scoped>
/* 与 naive-ui 表单圆角 / 边框色口径一致 */
.md-editor-shell {
  border-radius: var(--app-radius-sm, 4px);
  border-color: var(--app-border);
  width: 100%;
}
/* 编辑区内边距收紧：表单场景正文更贴近边缘（CodeMirror 内容层） */
.md-editor-shell :deep(.cm-content) {
  padding: 8px 12px;
}
/* 预览与展示侧（MarkdownView）口径一致：图片限宽 50%，不占满整行 */
.md-editor-shell :deep(img) {
  max-width: 50%;
}
</style>
