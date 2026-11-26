<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { X } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const props = withDefaults(
  defineProps<{
    modelValue: number | null
    id?: string
    disabled?: boolean
  }>(),
  { id: undefined, disabled: false },
)

const emit = defineEmits<{ 'update:modelValue': [value: number | null] }>()
const { t } = useI18n()

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

/** 时间戳 → input[type=datetime-local] 所需的本地时间字符串 */
const inputValue = computed(() => {
  if (props.modelValue == null) return ''
  const date = new Date(props.modelValue)
  if (Number.isNaN(date.getTime())) return ''
  const day = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
  return `${day}T${pad(date.getHours())}:${pad(date.getMinutes())}`
})

function onInput(value: string | number): void {
  const text = String(value)
  if (!text) {
    emit('update:modelValue', null)
    return
  }
  const parsed = new Date(text).getTime()
  emit('update:modelValue', Number.isNaN(parsed) ? null : parsed)
}
</script>

<template>
  <div class="flex items-center gap-1.5">
    <Input
      :id="id"
      type="datetime-local"
      :model-value="inputValue"
      :disabled="disabled"
      class="h-9 flex-1 text-[13px] [color-scheme:light] dark:[color-scheme:dark]"
      @update:model-value="onInput"
    />
    <Button
      v-if="modelValue != null && !disabled"
      variant="ghost"
      size="icon-sm"
      type="button"
      :aria-label="t('action.reset')"
      @click="emit('update:modelValue', null)"
    >
      <X class="size-3.5" />
    </Button>
  </div>
</template>