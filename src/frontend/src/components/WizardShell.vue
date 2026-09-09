<script setup lang="ts">
/**
 * 页眉卡片壳：卡片头（标题 + 可选步骤序号 + 右侧动作）。
 * 出题向导三步骤页传 step / total 展示序号；非向导页（如首页）不传 step，
 * 仅复用「标题 + 动作」的页眉结构。线性导航由各页动作按钮承担。
 */
import { computed } from 'vue'

const props = defineProps<{
  /** 当前步骤（1 起）；不传 = 非向导复用，隐藏步骤序号 */
  step?: 1 | 2 | 3
  /** 步骤总数（出题向导 3 步；两步向导传 2） */
  total?: 2 | 3
  /** 卡片头标题 */
  title: string
}>()

const stepLabel = computed(() => (props.step ? `${props.step} / ${props.total ?? 3}` : ''))
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
          <span v-if="stepLabel" class="card-head__step">{{ stepLabel }}</span>
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
