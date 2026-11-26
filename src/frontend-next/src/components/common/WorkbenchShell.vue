<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    description?: string
  }>(),
  { title: '', description: '' },
)
</script>

<template>
  <div class="flex h-[calc(100dvh-3.5rem)] flex-col px-4 pb-4 pt-3 md:px-6">
    <header
      v-if="title || $slots.actions || $slots.title"
      class="flex shrink-0 flex-wrap items-end justify-between gap-2 pb-3"
    >
      <div class="min-w-0">
        <slot name="title">
          <h1 class="text-xl font-semibold leading-tight tracking-tight">{{ title }}</h1>
        </slot>
        <p v-if="description" class="mt-1 max-w-[78ch] text-[13px] leading-5 text-muted-foreground">
          {{ description }}
        </p>
      </div>
      <div v-if="$slots.actions" class="flex flex-wrap items-center gap-2">
        <slot name="actions" />
      </div>
    </header>

    <div v-if="$slots.toolbar" class="mb-3 shrink-0">
      <slot name="toolbar" />
    </div>

    <slot />
  </div>
</template>
