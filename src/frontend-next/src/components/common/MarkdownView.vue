<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import { highlightCode } from '@/components/ui/code-block'
import { renderMarkdown } from '@/utils/markdown'
import 'katex/dist/katex.min.css'

const props = defineProps<{ source: string | null | undefined; wrapCode?: boolean }>()
const html = computed(() => renderMarkdown(props.source))
const root = ref<HTMLElement>()

/** Markdown 里的 ```cpp / ```python 等代码块统一映射到 Shiki 语言 */
const LANGUAGE_ALIASES: Record<string, string> = {
  'c++': 'cpp',
  cpp17: 'cpp',
  cxx: 'cpp',
  java21: 'java',
  'python3.12': 'python',
  py3: 'python',
  python3: 'python',
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function styleString(style: Record<string, string> | undefined): string {
  if (!style) return ''
  return Object.entries(style)
    .map(([key, value]) => `${key}:${String(value).replace(/"/g, "'")}`)
    .join(';')
}

/** v-html 渲染后再用 Shiki 给 fenced code 补上语法高亮 */
async function highlightBlocks(): Promise<void> {
  const element = root.value
  if (!element) return
  const current = html.value
  const blocks = Array.from(element.querySelectorAll<HTMLElement>('pre > code'))
  await Promise.all(
    blocks.map(async (block) => {
      if (block.dataset.highlighted === 'true') return
      const languageClass = Array.from(block.classList).find((name) =>
        name.startsWith('language-'),
      )
      if (!languageClass) return
      const language = languageClass.slice('language-'.length).toLowerCase()
      const source = block.textContent ?? ''
      if (!source.trim()) return
      const lines = await highlightCode(source, LANGUAGE_ALIASES[language] ?? language)
      if (!lines || html.value !== current) return
      block.innerHTML = lines
        .map((line) =>
          line.length === 0
            ? '\n'
            : line
                .map(
                  (token) =>
                    `<span class="shiki-token" style="${styleString(token.htmlStyle)}">${escapeHtml(token.content)}</span>`,
                )
                .join(''),
        )
        .join('\n')
      block.dataset.highlighted = 'true'
    }),
  )
}

watch(
  html,
  async () => {
    await nextTick()
    void highlightBlocks()
  },
  { immediate: true },
)

onMounted(() => {
  void highlightBlocks()
})
</script>

<template>
  <div ref="root" class="markdown" :class="{ 'markdown-wrap-code': wrapCode }" v-html="html" />
</template>