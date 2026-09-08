<script setup lang="ts">
/**
 * 图标包装（迁移兼容层，替代原 n-icon）：包一层内联 flex，
 * 统一控制 element-plus 图标（SVG，1em 自适应）的尺寸与颜色。
 */
import type { CSSProperties } from 'vue'
import { computed } from 'vue'

const props = defineProps<{
  /** 图标组件（@element-plus/icons-vue） */
  component?: unknown
  /** px 尺寸（1em 基准的 SVG 图标经 font-size 缩放） */
  size?: number | string
  color?: string
}>()

const style = computed<CSSProperties>(() => {
  const s: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
  }
  if (props.size !== undefined)
    s.fontSize = typeof props.size === 'number' ? `${props.size}px` : props.size
  if (props.color) s.color = props.color
  return s
})
</script>

<template>
  <span class="app-icon" :style="style">
    <component :is="props.component" v-if="props.component" />
    <slot v-else />
  </span>
</template>

<style scoped>
.app-icon > svg {
  width: 1em;
  height: 1em;
}
</style>
