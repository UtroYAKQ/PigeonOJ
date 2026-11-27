<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    description?: string
    width?: 'default' | 'narrow'
    /** 内容区撑满主可视高度，供整页空态/加载态垂直居中 */
    fill?: boolean
  }>(),
  { fill: false },
)
</script>

<template>
  <div
    class="mx-auto w-full"
    :class="[
      width === 'narrow' ? 'max-w-[1160px]' : 'max-w-[1360px]',
      fill ? 'flex h-full min-h-0 flex-col' : '',
    ]"
  >
    <div class="px-4 sm:px-6" :class="fill ? 'flex min-h-0 flex-1 flex-col py-4' : 'pb-16 pt-4'">
      <header
        v-if="title || $slots.actions || $slots.title"
        class="flex flex-col gap-2 pb-4 md:flex-row md:items-end md:justify-between"
      >
        <div class="min-w-0">
          <slot name="title">
            <h1 class="text-xl font-semibold leading-tight tracking-tight">{{ title }}</h1>
          </slot>
          <p
            v-if="description"
            class="mt-1 max-w-[78ch] text-[13px] leading-5 text-muted-foreground"
          >
            {{ description }}
          </p>
        </div>
        <div v-if="$slots.actions" class="flex flex-wrap items-center gap-2 md:justify-end">
          <slot name="actions" />
        </div>
      </header>
      <slot />
    </div>
  </div>
</template>