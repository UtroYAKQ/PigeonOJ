<script setup lang="ts">
/** 列表卡片外壳：整卡可点击且支持键盘 Enter / Space 触发，内容由领域卡片填充 */
const emit = defineEmits<{ select: [] }>()

function onKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Enter' && event.key !== ' ') return
  event.preventDefault()
  emit('select')
}
</script>

<template>
  <div
    role="button"
    tabindex="0"
    class="group flex h-full w-full cursor-pointer flex-col rounded-xl border border-border bg-card p-4 text-left transition-colors hover:border-foreground/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    @click="emit('select')"
    @keydown="onKeydown"
  >
    <slot />
  </div>
</template>
