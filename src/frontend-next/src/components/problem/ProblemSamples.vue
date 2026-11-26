<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Check, Copy } from '@lucide/vue'

import MarkdownView from '@/components/common/MarkdownView.vue'
import { TONE_TEXT_CLASSES } from '@/components/common/tone'
import { Button } from '@/components/ui/button'
import { copyToClipboard } from '@/utils/clipboard'
import { message } from '@/utils/feedback'

defineProps<{
  samples: Array<{ name: string; input: string; output: string; explanation?: string }>
}>()

const { t } = useI18n()
const copiedKeys = ref<Set<string>>(new Set())

async function copyText(text: string, key: string): Promise<void> {
  if (!(await copyToClipboard(text))) return
  copiedKeys.value.add(key)
  message.success(t('problems.detail.copied'))
  window.setTimeout(() => copiedKeys.value.delete(key), 1500)
}
</script>

<template>
  <div v-if="samples.length" class="grid gap-5">
    <div v-for="(sample, index) in samples" :key="index">
      <p class="mb-1.5 text-[12px] font-semibold text-muted-foreground">
        #{{ index + 1 }} {{ sample.name }}
      </p>

      <div class="grid gap-2">
        <div class="overflow-hidden rounded-lg border border-border">
          <div class="flex items-center justify-between py-0.5 pl-3 pr-1">
            <span class="text-[12px] text-muted-foreground">{{ t('problems.detail.stdin') }}</span>
            <Button
              variant="ghost"
              size="icon-xs"
              :aria-label="t('action.copy')"
              @click="copyText(sample.input, `${index}-in`)"
            >
              <Check v-if="copiedKeys.has(`${index}-in`)" class="size-3.5" :class="TONE_TEXT_CLASSES.success" />
              <Copy v-else class="size-3.5" />
            </Button>
          </div>
          <pre
            class="max-h-[240px] min-h-[42px] overflow-auto whitespace-pre-wrap break-all px-3 pb-2.5 font-mono text-[12px] leading-6"
            >{{ sample.input || t('problems.detail.noOutput') }}</pre>
        </div>

        <div class="overflow-hidden rounded-lg border border-border">
          <div class="flex items-center justify-between py-0.5 pl-3 pr-1">
            <span class="text-[12px] text-muted-foreground">{{
              t('problems.detail.expected')
            }}</span>
            <Button
              variant="ghost"
              size="icon-xs"
              :aria-label="t('action.copy')"
              @click="copyText(sample.output, `${index}-out`)"
            >
              <Check v-if="copiedKeys.has(`${index}-out`)" class="size-3.5" :class="TONE_TEXT_CLASSES.success" />
              <Copy v-else class="size-3.5" />
            </Button>
          </div>
          <pre
            class="max-h-[240px] min-h-[42px] overflow-auto whitespace-pre-wrap break-all px-3 pb-2.5 font-mono text-[12px] leading-6"
            >{{ sample.output || t('problems.detail.noOutput') }}</pre>
        </div>
      </div>

      <div v-if="sample.explanation" class="mt-2">
        <p class="mb-1 text-[12px] font-semibold text-muted-foreground">
          {{ t('problems.detail.explanation') }}
        </p>
        <MarkdownView :source="sample.explanation" class="text-[13px]" />
      </div>
    </div>
  </div>
  <p v-else class="text-[13px] text-muted-foreground">{{ t('problems.detail.noSamples') }}</p>
</template>
