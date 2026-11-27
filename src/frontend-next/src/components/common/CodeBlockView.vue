<script setup lang="ts">
import { computed } from 'vue'
import { FileCode2 } from '@lucide/vue'

import {
  CodeBlock,
  CodeBlockActions,
  CodeBlockContent,
  CodeBlockCopyButton,
  CodeBlockHeader,
  CodeBlockLine,
  CodeBlockTitle,
  CodeBlockToken,
  useHighlightedCode,
} from '@/components/ui/code-block'

/** 只读代码展示：标题/语言 + Shiki 语法高亮 + 行号 + 复制。 */
const props = withDefaults(
  defineProps<{
    code: string
    language: string
    title?: string
    maxHeight?: string
  }>(),
  { title: '', maxHeight: '' },
)

const LANGUAGE_LABELS: Record<string, string> = {
  cpp17: 'C++17',
  'python3.12': 'Python 3.12',
  java21: 'Java 21',
}

const label = computed(
  () => props.title || LANGUAGE_LABELS[props.language] || props.language || 'Code',
)
const lines = useHighlightedCode(
  () => props.code,
  () => props.language,
)
</script>

<template>
  <CodeBlock>
    <CodeBlockHeader>
      <CodeBlockTitle>
        <FileCode2 />
        {{ label }}
      </CodeBlockTitle>
      <CodeBlockActions>
        <CodeBlockCopyButton :value="code" />
      </CodeBlockActions>
    </CodeBlockHeader>
    <CodeBlockContent :class="maxHeight || undefined" line-numbers>
      <CodeBlockLine v-for="(line, index) in lines" :key="index">
        <CodeBlockToken v-for="(token, tokenIndex) in line" :key="tokenIndex" :token="token" />
      </CodeBlockLine>
    </CodeBlockContent>
  </CodeBlock>
</template>