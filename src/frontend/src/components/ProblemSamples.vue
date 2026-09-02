<script setup lang="ts">
/**
 * 题目样例展示（极简风）：输入 / 输出上下排布，各自独立展示框；
 * 框头左侧弱化文字标签，右侧复制按钮（复制成功后图标短暂切换为对勾）。
 * 样例解释（explanation，Markdown）按组渲染于样例框之后，空则不展示。
 */
import { Check, CopyDocument } from '@element-plus/icons-vue'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { copyToClipboard } from '@/utils/clipboard'
import { message } from '@/utils/feedback'
import MarkdownView from '@/components/MarkdownView.vue'

defineProps<{
  samples: Array<{ name: string; input: string; output: string; explanation?: string }>
}>()

const { t } = useI18n()

/** 复制成功后图标切换为对勾的展示键（{样例序号}-{in|out}），1.5s 后还原 */
const copiedKeys = ref<Set<string>>(new Set())
const COPIED_RESET_MS = 1500

function isCopied(key: string) {
  return copiedKeys.value.has(key)
}

async function copyText(text: string, key: string) {
  if (!(await copyToClipboard(text))) return
  copiedKeys.value.add(key)
  message.success(t('problems.detail.copied'))
  window.setTimeout(() => copiedKeys.value.delete(key), COPIED_RESET_MS)
}
</script>

<template>
  <div v-if="samples.length" class="samples">
    <div v-for="(sample, index) in samples" :key="index" class="sample-block">
      <p class="sample-block__head">#{{ index + 1 }} {{ sample.name }}</p>

      <div class="sample-panes">
        <!-- 样例输入 -->
        <div class="sample-pane">
          <div class="sample-pane__head">
            <span>{{ t('problems.detail.stdin') }}</span>
            <n-button
              quaternary
              circle
              size="tiny"
              :aria-label="t('action.copy')"
              :title="t('action.copy')"
              @click="copyText(sample.input, `${index}-in`)"
            >
              <n-icon v-if="isCopied(`${index}-in`)" :size="14" color="var(--app-success)">
                <Check />
              </n-icon>
              <n-icon v-else :size="14">
                <CopyDocument />
              </n-icon>
            </n-button>
          </div>
          <pre class="sample-pane__body">{{ sample.input || t('problems.detail.noOutput') }}</pre>
        </div>

        <!-- 样例输出 -->
        <div class="sample-pane">
          <div class="sample-pane__head">
            <span>{{ t('problems.detail.expected') }}</span>
            <n-button
              quaternary
              circle
              size="tiny"
              :aria-label="t('action.copy')"
              :title="t('action.copy')"
              @click="copyText(sample.output, `${index}-out`)"
            >
              <n-icon v-if="isCopied(`${index}-out`)" :size="14" color="var(--app-success)">
                <Check />
              </n-icon>
              <n-icon v-else :size="14">
                <CopyDocument />
              </n-icon>
            </n-button>
          </div>
          <pre class="sample-pane__body">{{ sample.output || t('problems.detail.noOutput') }}</pre>
        </div>
      </div>

      <!-- 样例解释：按组可选，空则不渲染 -->
      <div v-if="sample.explanation" class="sample-explanation">
        <p class="sample-explanation__label">{{ t('problems.detail.explanation') }}</p>
        <MarkdownView :source="sample.explanation" class="sample-explanation__body" />
      </div>
    </div>
  </div>
  <n-empty v-else size="small" :description="t('problems.detail.noSamples')" />
</template>

<style scoped>
.samples {
  display: grid;
  gap: 16px;
}
/* 样例标题：仅一行弱化文字，不再包边框 / 底色 / 序号 chip */
.sample-block__head {
  margin: 0 0 6px;
  color: var(--app-text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.sample-panes {
  display: grid;
  gap: 8px;
}
/* 样例解释：弱化标签 + Markdown 正文（≤64KB，按组渲染） */
.sample-explanation {
  margin-top: 8px;
}
.sample-explanation__label {
  margin: 0 0 4px;
  color: var(--app-text-secondary);
  font-size: 12px;
  font-weight: 600;
}
.sample-explanation__body {
  font-size: 13px;
}
.sample-pane {
  overflow: hidden;
  border: 1px solid var(--app-border);
  border-radius: 6px;
}
.sample-pane__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 4px 2px 10px;
  color: var(--app-text-secondary);
  font-size: 12px;
}
.sample-pane__body {
  max-height: 240px;
  min-height: 42px;
  margin: 0;
  overflow: auto;
  padding: 10px 12px;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: ui-monospace, SFMono-Regular, Consolas, 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
}
</style>
