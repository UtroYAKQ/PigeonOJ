<script setup lang="ts">
/**
 * 出题向导壳：卡片头（标题 + 步骤序号 + 右侧动作）。
 * 三个步骤页（题面 / 样例与测试点 / 验题与发布）共用，各页只提供标题、动作按钮与主体内容；
 * 线性导航由各页「上一步 / 下一步」按钮承担，不展示横向步骤条。
 */
import { computed } from 'vue'

const props = defineProps<{
  /** 当前步骤（1 起），用于卡片头步骤序号 */
  step: 1 | 2 | 3
  /** 卡片头标题 */
  title: string
}>()

const stepLabel = computed(() => `${props.step} / 3`)
</script>

<template>
  <!-- 内边距较 n-card 默认（19/24/20）收窄：向导页以表单 / 编辑器为主体，减少两侧空转区 -->
  <n-card
    :bordered="false"
    :header-style="{ padding: '12px 16px' }"
    :content-style="{ padding: '12px 16px 16px' }"
  >
    <template #header>
      <div class="wizard-shell__head">
        <div class="card-head__title">
          <span>{{ title }}</span>
          <span class="card-head__step">{{ stepLabel }}</span>
        </div>
        <!-- 向导导航收进卡片头：无需滚动即可见（上一步 / 下一步 / 取消等由各页放置） -->
        <div class="wizard-shell__actions">
          <slot name="actions" />
        </div>
      </div>
    </template>

    <slot />
  </n-card>
</template>

<style scoped>
.wizard-shell__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}
.wizard-shell__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
