<script setup lang="ts">
import { computed } from 'vue'

import { renderMarkdown } from '@/utils/markdown'
import 'katex/dist/katex.min.css'

const props = defineProps<{ source: string | null | undefined; wrapCode?: boolean }>()
const html = computed(() => renderMarkdown(props.source))
</script>

<template>
  <div class="markdown" :class="{ 'markdown-wrap-code': wrapCode }" v-html="html" />
</template>
