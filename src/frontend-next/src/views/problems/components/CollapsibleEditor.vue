<script setup lang="ts">
import { ref, watch } from 'vue'
import { Minus, Plus } from '@lucide/vue'

import MarkdownEditor from '@/components/common/MarkdownEditor.vue'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'

/**
 * 可折叠的 Markdown 编辑区（题面说明 / 官方题解）：
 * 首次展开才挂载编辑器，避免在 0 高折叠容器中初始化。
 */
const props = withDefaults(
  defineProps<{
    title: string
    addLabel: string
    hideLabel: string
    modelValue: string
    minHeight?: string
    compact?: boolean
    defaultOpen?: boolean
  }>(),
  { minHeight: '180px', compact: false, defaultOpen: false },
)

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const open = ref(props.defaultOpen)
const mounted = ref(props.defaultOpen)

watch(open, (value) => {
  if (value) mounted.value = true
})

watch(
  () => props.defaultOpen,
  (value) => {
    if (!value) return
    open.value = true
    mounted.value = true
  },
)
</script>

<template>
  <Collapsible v-model:open="open">
    <div class="flex items-center justify-between border-b border-dashed border-border pb-2">
      <h3 class="text-[13.5px] font-semibold">{{ props.title }}</h3>
      <CollapsibleTrigger as-child>
        <Button variant="ghost" size="xs" class="text-[12px] text-muted-foreground">
          <Minus v-if="open" class="size-3.5" />
          <Plus v-else class="size-3.5" />
          {{ open ? props.hideLabel : props.addLabel }}
        </Button>
      </CollapsibleTrigger>
    </div>
    <CollapsibleContent>
      <div class="pt-2.5">
        <MarkdownEditor
          v-if="mounted"
          :model-value="props.modelValue"
          :min-height="props.minHeight"
          :compact="props.compact"
          @update:model-value="emit('update:modelValue', $event)"
        />
      </div>
    </CollapsibleContent>
  </Collapsible>
</template>