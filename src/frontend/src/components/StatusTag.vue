<script setup lang="ts">
/**
 * 提交/测试点状态标签：统一 status → 颜色映射与 i18n 文案，
 * 供提交历史弹窗、结果页测试点表等表格列渲染复用。
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { submissionStatusTagType } from '@/constants/submissionStatus'

const props = defineProps<{ status: string }>()

const { t } = useI18n()
const type = computed(() => submissionStatusTagType(props.status))
</script>

<template>
  <n-tag size="small" :type="type" :bordered="false">
    {{ t(`problems.status.${status}`) }}
  </n-tag>
</template>
