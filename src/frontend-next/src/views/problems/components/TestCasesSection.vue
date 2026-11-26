<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Plus } from '@lucide/vue'

import TestCaseImporter from '@/components/problem/TestCaseImporter.vue'
import { Button } from '@/components/ui/button'
import type { TestCaseDraft } from '@/types'
import CaseCard from './CaseCard.vue'

/** 正式测试点编辑区：新增 / 删除 / ZIP 导入（保存时由宿主按行 diff 增量提交） */
const props = defineProps<{ modelValue: TestCaseDraft[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: TestCaseDraft[]] }>()

const { t } = useI18n()

function patch(index: number, changes: Partial<TestCaseDraft>): void {
  emit(
    'update:modelValue',
    props.modelValue.map((item, i) => (i === index ? { ...item, ...changes } : item)),
  )
}

function addCase(): void {
  emit('update:modelValue', [
    ...props.modelValue,
    {
      name: String(props.modelValue.length + 1),
      input: '',
      expected_output: '',
      sort_order: props.modelValue.length + 1,
    },
  ])
}

function removeCase(index: number): void {
  emit(
    'update:modelValue',
    props.modelValue.filter((_, i) => i !== index),
  )
}

function importCases(items: TestCaseDraft[]): void {
  emit(
    'update:modelValue',
    items.map((item, index) => ({
      ...item,
      name: item.name || String(index + 1),
      sort_order: index + 1,
    })),
  )
}
</script>

<template>
  <section>
    <div class="flex flex-wrap items-end justify-between gap-2">
      <div>
        <h2 class="text-lg font-medium">{{ t('problems.create.caseTitle') }}</h2>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('problems.create.casesHint') }}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <TestCaseImporter @imported="importCases" />
        <Button size="sm" @click="addCase">
          <Plus class="size-4" />
          {{ t('problems.create.addCase') }}
        </Button>
      </div>
    </div>
    <div v-if="props.modelValue.length" class="mt-2.5 grid gap-3">
      <CaseCard
        v-for="(item, index) in props.modelValue"
        :key="item.id ?? `new-${index}`"
        :index="index"
        :name="item.name"
        :input="item.input"
        :output="item.expected_output"
        :staged="item.staged"
        name-editable
        @update:name="patch(index, { name: $event })"
        @update:input="patch(index, { input: $event })"
        @update:output="patch(index, { expected_output: $event })"
        @remove="removeCase(index)"
      />
    </div>
    <p v-else class="mt-2 text-[13px] text-muted-foreground">
      {{ t('problems.create.contentRequired') }}
    </p>
  </section>
</template>
