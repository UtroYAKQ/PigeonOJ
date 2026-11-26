<script setup lang="ts">
import type { Component } from 'vue'

import { TONE_NOTICE_CLASSES, type Tone } from '@/components/common/tone'

withDefaults(defineProps<{ tone?: Tone; icon?: Component }>(), {
  tone: 'info',
  icon: undefined,
})
</script>

<template>
  <div
    class="flex items-start gap-2 rounded-lg border px-3.5 py-2.5 text-[12.5px] leading-5"
    :class="TONE_NOTICE_CLASSES[tone]"
  >
    <component :is="icon" v-if="icon" class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
    <div class="min-w-0 flex-1">
      <slot />
    </div>
  </div>
</template>