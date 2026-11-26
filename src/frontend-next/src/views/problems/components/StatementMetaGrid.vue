<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ProblemTagItem } from '@/types'
import StatementTagField from './StatementTagField.vue'

/** 题面基础信息元数据行：标签 / 可见性 / 限制 / 难度分 */
defineProps<{
  visibilityOptions: Array<{ label: string; value: string }>
  tagOptions: ProblemTagItem[]
  showVisibility?: boolean
}>()

const tags = defineModel<string[]>('tags', { required: true })
const visibility = defineModel<string>('visibility', { required: true })
const timeLimit = defineModel<string>('timeLimit', { required: true })
const memoryLimit = defineModel<string>('memoryLimit', { required: true })
const difficulty = defineModel<string>('difficulty', { required: true })

const { t } = useI18n()
</script>

<template>
  <div
    class="grid gap-3 sm:grid-cols-2"
    :class="
      showVisibility === false
        ? 'xl:grid-cols-[minmax(0,1.6fr)_repeat(3,minmax(0,1fr))]'
        : 'xl:grid-cols-[minmax(0,1.6fr)_repeat(4,minmax(0,1fr))]'
    "
  >
    <div class="space-y-1.5 sm:col-span-2 xl:col-span-1">
      <Label class="text-[13px]">{{ t('problems.create.tags') }}</Label>
      <StatementTagField v-model="tags" :tag-options="tagOptions" />
    </div>
    <div v-if="showVisibility !== false" class="space-y-1.5">
      <Label class="text-[13px]">{{ t('problems.create.visibility') }}</Label>
      <Select v-model="visibility">
        <SelectTrigger class="h-9 w-full text-[13px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem v-for="item in visibilityOptions" :key="item.value" :value="item.value">
            {{ item.label }}
          </SelectItem>
        </SelectContent>
      </Select>
    </div>
    <div class="space-y-1.5">
      <Label class="text-[13px]">{{ t('problems.create.timeLimit') }}</Label>
      <Input v-model="timeLimit" type="number" min="1" class="h-9 text-[13px] tabular-nums" />
    </div>
    <div class="space-y-1.5">
      <Label class="text-[13px]">{{ t('problems.create.memoryLimit') }}</Label>
      <Input v-model="memoryLimit" type="number" min="16" class="h-9 text-[13px] tabular-nums" />
    </div>
    <div class="space-y-1.5">
      <Label class="text-[13px]">{{ t('problems.create.difficulty') }}</Label>
      <Input
        v-model="difficulty"
        type="number"
        min="0"
        class="h-9 text-[13px] tabular-nums"
        :placeholder="t('problems.create.difficultyPlaceholder')"
      />
    </div>
  </div>
</template>
