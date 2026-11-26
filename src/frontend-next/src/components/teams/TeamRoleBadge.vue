<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import ToneBadge from '@/components/common/ToneBadge.vue'
import type { Tone } from '@/components/common/tone'
import type { TeamRoleType } from '@/types'

const props = defineProps<{ role: TeamRoleType }>()
const { t } = useI18n()

/** 角色 = 色点 + 文本（不单一靠颜色传递语义），对齐旧团队列表 / 成员行的三级角色 */
const tone = computed<Tone>(() => {
  if (props.role === 'creator') return 'warning'
  if (props.role === 'admin') return 'info'
  return 'default'
})
</script>

<template>
  <ToneBadge :tone="tone" :label="t(`teams.role.${role}`)" dot />
</template>