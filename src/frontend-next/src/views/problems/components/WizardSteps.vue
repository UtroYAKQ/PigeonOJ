<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronRight } from '@lucide/vue'

/** 出题向导步骤条：纯展示进度（不做点击切换，避免未保存内容丢失） */
const props = defineProps<{ current: 1 | 2 | 3 }>()

const { t } = useI18n()

const steps = computed(() =>
  [
    { step: 1 as const, label: t('problems.wizard.basic') },
    { step: 2 as const, label: t('problems.wizard.cases') },
    { step: 3 as const, label: t('problems.wizard.verifyPublish') },
  ].map((item) => ({
    ...item,
    active: item.step === props.current,
    done: item.step < props.current,
  })),
)
</script>

<template>
  <ol class="flex flex-wrap items-center gap-x-2 gap-y-1.5 text-[12px]">
    <li
      v-for="(item, index) in steps"
      :key="item.step"
      class="flex items-center gap-2"
      :aria-current="item.active ? 'step' : undefined"
    >
      <span
        class="grid size-5 place-items-center rounded-full border text-[11px] font-medium tabular-nums"
        :class="
          item.active
            ? 'border-foreground bg-foreground text-background'
            : item.done
              ? 'border-border bg-muted text-foreground'
              : 'border-border text-muted-foreground'
        "
      >
        {{ item.step }}
      </span>
      <span :class="item.active ? 'font-medium text-foreground' : 'text-muted-foreground'">
        {{ item.label }}
      </span>
      <ChevronRight
        v-if="index < steps.length - 1"
        class="size-3.5 shrink-0 text-muted-foreground/60"
      />
    </li>
  </ol>
</template>
