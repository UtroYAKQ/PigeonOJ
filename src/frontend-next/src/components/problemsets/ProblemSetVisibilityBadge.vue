<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import ToneBadge from '@/components/common/ToneBadge.vue'
import type { TagType } from '@/constants/dict'
import { problemSetVisibilityKey } from '@/utils/visibilityLabel'

const props = defineProps<{ visibility: string }>()
const { t } = useI18n()

/** 公开 / 团队可见 info；私有 danger（团队题单恒 team_visible，admin_visible 已下线） */
const tone = computed<TagType>(() => {
  if (props.visibility === 'public' || props.visibility === 'team_visible') return 'info'
  return 'danger'
})
</script>

<template>
  <ToneBadge :tone="tone" :label="t(problemSetVisibilityKey(visibility))" />
</template>
