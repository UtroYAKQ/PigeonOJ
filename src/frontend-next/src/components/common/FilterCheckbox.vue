<script setup lang="ts">
/**
 * 列表工具条勾选筛选项：整行 label 可点击，视觉与题库列表保持一致。
 * 只负责展示与发出状态变更，查询由页面在 update:modelValue 中触发。
 */
import { Checkbox } from '@/components/ui/checkbox'

defineProps<{
  modelValue: boolean
  label: string
  id?: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

function onUpdate(value: boolean | 'indeterminate'): void {
  emit('update:modelValue', value === true)
}
</script>

<template>
  <label
    :for="id"
    class="flex cursor-pointer items-center gap-1.5 text-[13px] text-muted-foreground"
  >
    <Checkbox
      :id="id"
      :model-value="modelValue"
      class="size-3.5"
      @update:model-value="onUpdate"
    />
    {{ label }}
  </label>
</template>
