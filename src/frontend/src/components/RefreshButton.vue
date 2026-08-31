<script setup lang="ts">
/**
 * 刷新按钮（docs/frontend.md「交互习惯」刷新按钮规范）：
 * icon-only 圆形幽灵按钮；加载中图标自旋表达状态。
 * 不使用 naive :loading —— 它会把图标整体替换为转圈组件，产生尺寸跳变与视觉突兀；
 * 查询进度由页面表格 / 内容区的 loading 遮罩承担。
 * aria-label 与 @click 经 attrs 透传到根按钮。
 */
import { Refresh } from '@element-plus/icons-vue'

defineProps<{ loading?: boolean }>()
</script>

<template>
  <n-button quaternary circle>
    <n-icon :component="Refresh" :class="{ 'is-spinning': loading }" />
  </n-button>
</template>

<style scoped>
.is-spinning {
  animation: app-icon-spin 0.8s linear infinite;
}
@keyframes app-icon-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
