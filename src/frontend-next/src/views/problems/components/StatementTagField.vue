<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Plus, X } from '@lucide/vue'

import TagPicker from '@/components/problem/TagPicker.vue'
import { Button } from '@/components/ui/button'
import type { ProblemTagItem } from '@/types'

/** 题面标签选择（最多 8 个激活标签；选择器弹出后由本组件维护已选名集合） */
const props = defineProps<{
  modelValue: string[]
  tagOptions: ProblemTagItem[]
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

const { t } = useI18n()
const pickerOpen = ref(false)

const MAX_TAGS = 8

const chosenNames = computed(() => new Set(props.modelValue))
const colorMap = computed(() => {
  const map = new Map<string, string>()
  for (const tag of props.tagOptions) {
    if (tag.color) map.set(tag.name, tag.color)
  }
  return map
})

function addTag(tag: ProblemTagItem): void {
  if (props.modelValue.length >= MAX_TAGS || chosenNames.value.has(tag.name)) return
  emit('update:modelValue', [...props.modelValue, tag.name])
}

function removeTag(name: string): void {
  emit(
    'update:modelValue',
    props.modelValue.filter((item) => item !== name),
  )
}
</script>

<template>
  <div class="space-y-1.5">
    <div class="flex min-h-6 flex-wrap items-center gap-1.5">
      <span
        v-for="name in modelValue"
        :key="name"
        class="inline-flex h-6 items-center gap-1 rounded-md border border-border pl-2 pr-1 text-[11.5px] text-muted-foreground"
        :style="
          colorMap.get(name)
            ? { borderColor: `${colorMap.get(name)}55`, color: colorMap.get(name) }
            : undefined
        "
      >
        {{ name }}
        <button
          type="button"
          class="grid size-4 place-items-center rounded-sm transition-colors hover:bg-muted"
          :aria-label="`${name} ${t('action.close')}`"
          @click="removeTag(name)"
        >
          <X class="size-3" />
        </button>
      </span>
      <span v-if="!modelValue.length" class="text-[13px] text-muted-foreground">
        {{ t('problems.create.tagsPlaceholder') }}
      </span>
    </div>

    <Button
      variant="outline"
      size="xs"
      :disabled="modelValue.length >= MAX_TAGS"
      @click="pickerOpen = true"
    >
      <Plus class="size-3.5" />
      {{ t('problems.create.addTag') }}
    </Button>

    <TagPicker v-model:show="pickerOpen" :chosen-names="chosenNames" @select="addTag" />
  </div>
</template>
