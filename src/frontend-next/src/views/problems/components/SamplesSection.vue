<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Plus } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import CaseCard from './CaseCard.vue'

interface SampleDraft {
  input: string
  output: string
  explanation: string
}

/** 展示样例编辑区（≤10 组；存 problems.samples，仅展示与自测，不参与判题） */
const props = defineProps<{ modelValue: SampleDraft[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: SampleDraft[]] }>()

const { t } = useI18n()
const MAX_SAMPLES = 10

function patch(index: number, changes: Partial<SampleDraft>): void {
  emit(
    'update:modelValue',
    props.modelValue.map((item, i) => (i === index ? { ...item, ...changes } : item)),
  )
}

function addSample(): void {
  if (props.modelValue.length >= MAX_SAMPLES) return
  emit('update:modelValue', [...props.modelValue, { input: '', output: '', explanation: '' }])
}

function removeSample(index: number): void {
  emit(
    'update:modelValue',
    props.modelValue.filter((_, i) => i !== index),
  )
}
</script>

<template>
  <section>
    <div class="flex flex-wrap items-end justify-between gap-2">
      <div>
        <h2 class="text-lg font-medium">{{ t('problems.detail.samples') }}</h2>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('problems.create.samplesHint') }}
        </p>
      </div>
      <Button
        variant="outline"
        size="sm"
        :disabled="props.modelValue.length >= MAX_SAMPLES"
        @click="addSample"
      >
        <Plus class="size-4" />
        {{ t('problems.create.addSample') }}
      </Button>
    </div>
    <div v-if="props.modelValue.length" class="mt-2.5 grid gap-3">
      <CaseCard
        v-for="(sample, index) in props.modelValue"
        :key="index"
        :index="index"
        :input="sample.input"
        :output="sample.output"
        :explanation="sample.explanation"
        accent
        show-explanation
        @update:input="patch(index, { input: $event })"
        @update:output="patch(index, { output: $event })"
        @update:explanation="patch(index, { explanation: $event })"
        @remove="removeSample(index)"
      />
    </div>
    <p v-else class="mt-2 text-[13px] text-muted-foreground">
      {{ t('problems.detail.noSamples') }}
    </p>
  </section>
</template>
