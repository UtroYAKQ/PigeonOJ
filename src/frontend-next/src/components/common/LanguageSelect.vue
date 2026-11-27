<script setup lang="ts">
import { computed } from 'vue'

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { languageOptions } from '@/constants/languages'
import type { ProblemLanguage } from '@/types'

const props = defineProps<{ modelValue: ProblemLanguage; class?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: ProblemLanguage] }>()

const value = computed({
  get: () => props.modelValue,
  set: (next: ProblemLanguage) => emit('update:modelValue', next),
})
</script>

<template>
  <Select v-model="value">
    <SelectTrigger class="h-9 w-[130px] text-[13px]" :class="props.class">
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      <SelectItem v-for="item in languageOptions" :key="item.value" :value="item.value">
        {{ item.label }}
      </SelectItem>
    </SelectContent>
  </Select>
</template>
