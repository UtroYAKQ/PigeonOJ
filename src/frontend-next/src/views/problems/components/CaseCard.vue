<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Trash2 } from '@lucide/vue'

import ToneBadge from '@/components/common/ToneBadge.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { TooltipHint } from '@/components/ui/tooltip'

/** 样例 / 测试点卡片：编号 + 可选名称 + 输入输出（+ 样例解释）与删除 */
const props = withDefaults(
  defineProps<{
    index: number
    /** 样例卡片用强调序号，正式测试点用中性序号，一眼区分两类卡片 */
    accent?: boolean
    nameEditable?: boolean
    staged?: boolean
    showExplanation?: boolean
  }>(),
  { accent: false, nameEditable: false, staged: false, showExplanation: false },
)

const emit = defineEmits<{ remove: [] }>()

const name = defineModel<string>('name', { default: '' })
const input = defineModel<string>('input', { required: true })
const output = defineModel<string>('output', { required: true })
const explanation = defineModel<string>('explanation', { default: '' })

const { t } = useI18n()
</script>

<template>
  <div class="rounded-lg border border-border bg-muted/30 p-3">
    <div class="flex flex-wrap items-center gap-2.5">
      <span
        class="grid size-6 shrink-0 place-items-center rounded-md border text-[12px] font-semibold tabular-nums"
        :class="
          props.accent
            ? 'border-foreground/15 bg-foreground text-background'
            : 'border-border bg-card text-muted-foreground'
        "
      >
        {{ props.index + 1 }}
      </span>
      <Input
        v-if="props.nameEditable"
        v-model="name"
        class="h-8 w-[180px] text-[12.5px]"
        :placeholder="t('problems.create.caseName')"
      />
      <ToneBadge v-if="props.staged" tone="warning" :label="t('problems.create.stagedBadge')" />
      <div class="flex-1" />
      <TooltipHint :text="t('problems.create.removeCase')">
        <Button
          variant="ghost"
          size="icon-xs"
          class="text-muted-foreground hover:text-destructive"
          :aria-label="t('problems.create.removeCase')"
          @click="emit('remove')"
        >
          <Trash2 class="size-3.5" />
        </Button>
      </TooltipHint>
    </div>

    <div class="mt-3 grid gap-3 md:grid-cols-2">
      <Textarea
        v-model="input"
        :rows="3"
        class="min-h-[84px] resize-y font-mono text-[12.5px] leading-5"
        :placeholder="t('problems.create.inputContent')"
        :aria-label="t('problems.create.inputContent')"
      />
      <Textarea
        v-model="output"
        :rows="3"
        class="min-h-[84px] resize-y font-mono text-[12.5px] leading-5"
        :placeholder="t('problems.create.outputContent')"
        :aria-label="t('problems.create.outputContent')"
      />
    </div>

    <Textarea
      v-if="props.showExplanation"
      v-model="explanation"
      :rows="2"
      class="mt-3 min-h-[56px] resize-y text-[12.5px] leading-5"
      :placeholder="t('problems.create.explanationPlaceholder')"
      :aria-label="t('problems.create.explanationPlaceholder')"
    />
  </div>
</template>
