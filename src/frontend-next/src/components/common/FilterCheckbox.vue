<script setup lang="ts">
/**
 * 列表工具条勾选筛选项：整行 label 可点击，视觉与题库列表保持一致。
 * 只负责展示与发出状态变更，查询由页面在 update:modelValue 中触发。
 */
defineProps<{
  modelValue: boolean
  label: string
  id?: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

function onChange(event: Event): void {
  emit('update:modelValue', (event.target as HTMLInputElement).checked)
}
</script>

<template>
  <label
    :for="id"
    class="flex cursor-pointer items-center gap-1.5 text-[13px] text-muted-foreground"
  >
    <input
      :id="id"
      :checked="modelValue"
      type="checkbox"
      class="size-3.5 accent-foreground"
      @change="onChange"
    />
    {{ label }}
  </label>
</template>
