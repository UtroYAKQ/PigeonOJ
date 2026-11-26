<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { ref } from 'vue'
import { Eye, EyeOff } from '@lucide/vue'
import { useI18n } from 'vue-i18n'

import { Input } from '@/components/ui/input'

const props = defineProps<{
  modelValue: string
  class?: HTMLAttributes['class']
  autocomplete?: string
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const { t } = useI18n()
const visible = ref(false)

function onInput(event: Event): void {
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}
</script>

<template>
  <div class="relative">
    <Input
      :model-value="props.modelValue"
      :type="visible ? 'text' : 'password'"
      :autocomplete="props.autocomplete"
      class="h-10 pr-10 text-[13.5px]"
      @input="onInput"
    />
    <button
      type="button"
      class="absolute inset-y-0 right-0 grid w-10 place-items-center text-muted-foreground transition-colors hover:text-foreground"
      :aria-label="visible ? t('app.hidePassword') : t('app.showPassword')"
      @click="visible = !visible"
    >
      <EyeOff v-if="visible" class="size-4" />
      <Eye v-else class="size-4" />
    </button>
  </div>
</template>
