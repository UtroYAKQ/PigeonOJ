<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from '@/utils/markdown'
import 'katex/dist/katex.min.css'

const props = defineProps<{ source: string | null | undefined }>()
const html = computed(() => renderMarkdown(props.source))
</script>
<template>
  <div class="markdown-view" v-html="html" />
</template>

<style scoped>
.markdown-view {
  line-height: 1.85;
  font-size: 14px;
  word-break: break-word;
}
.markdown-view :deep(h1),
.markdown-view :deep(h2),
.markdown-view :deep(h3),
.markdown-view :deep(h4) {
  margin: 1.1em 0 0.5em;
  font-weight: 700;
  letter-spacing: -0.01em;
}
.markdown-view :deep(h1) {
  font-size: 20px;
}
.markdown-view :deep(h2) {
  font-size: 17px;
}
.markdown-view :deep(h3),
.markdown-view :deep(h4) {
  font-size: 15px;
}
.markdown-view :deep(> :first-child) {
  margin-top: 0;
}
.markdown-view :deep(p) {
  margin: 0.6em 0;
}
.markdown-view :deep(ul),
.markdown-view :deep(ol) {
  margin: 0.6em 0;
  padding-left: 1.5em;
}
.markdown-view :deep(li) {
  margin: 0.25em 0;
}
.markdown-view :deep(a) {
  color: var(--app-primary);
  text-decoration: none;
}
.markdown-view :deep(a:hover) {
  text-decoration: underline;
}
.markdown-view :deep(blockquote) {
  margin: 0.8em 0;
  padding: 8px 14px;
  border-left: 3px solid rgba(244, 81, 30, 0.35);
  border-radius: 0 var(--app-radius-lg) var(--app-radius-lg) 0;
  background: var(--app-surface-muted);
  color: var(--app-text-muted);
}
.markdown-view :deep(code) {
  padding: 2px 6px;
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
  border: 1px solid var(--app-border);
  font-family: ui-monospace, SFMono-Regular, Consolas, 'Courier New', monospace;
  font-size: 13px;
}
.markdown-view :deep(pre) {
  margin: 0.8em 0;
  padding: 12px 14px;
  overflow: auto;
  border-radius: var(--app-radius);
  border: 1px solid var(--app-border);
  background: var(--app-surface-muted);
}
.markdown-view :deep(pre code) {
  padding: 0;
  border: none;
  background: transparent;
  white-space: pre;
}
.markdown-view :deep(img) {
  /* 题面插图默认限宽 50%：截图类大图不占满整行（小图不受影响） */
  max-width: 50%;
  border-radius: var(--app-radius);
}
.markdown-view :deep(table) {
  margin: 0.8em 0;
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.markdown-view :deep(th),
.markdown-view :deep(td) {
  border: 1px solid var(--app-border);
  padding: 7px 12px;
  text-align: left;
}
.markdown-view :deep(th) {
  background: var(--app-surface-muted);
  font-weight: 500;
}
.markdown-view :deep(hr) {
  margin: 1.2em 0;
  border: none;
  border-top: 1px solid var(--app-border);
}
</style>
