<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import defaultContestAvatar from '@/assets/avatars/default-contest.svg'
import defaultTeamAvatar from '@/assets/avatars/default-team.svg'
import defaultUserAvatar from '@/assets/avatars/default-user.svg'

type AvatarKind = 'user' | 'team' | 'contest'

const props = withDefaults(
  defineProps<{
    /** 头像图片地址（站内完整 URL 或可信外链）；空值或加载失败时回退默认头像 */
    src?: string | null
    /** 实体名称，用作 img alt；缺省时整块视为装饰 */
    name?: string | null
    /** 边长（px），宽高一致 */
    size?: number
    /** 圆形（默认）；false 时为 radius 圆角矩形 */
    round?: boolean
    /** round=false 时的圆角半径（px） */
    radius?: number
    /** 1px 描边（列表卡片场景） */
    bordered?: boolean
    /** 实体类型，决定默认头像图 */
    kind?: AvatarKind
  }>(),
  {
    src: null,
    name: null,
    size: 40,
    round: true,
    radius: 8,
    bordered: false,
    kind: 'user',
  },
)

const DEFAULT_AVATARS: Record<AvatarKind, string> = {
  user: defaultUserAvatar,
  team: defaultTeamAvatar,
  contest: defaultContestAvatar,
}

// 外链头像失效 / 加载失败时降级默认头像，避免碎图；src 变化后复位重试
const loadFailed = ref(false)
watch(
  () => props.src,
  () => {
    loadFailed.value = false
  },
)

const effectiveSrc = computed(() =>
  !props.src || loadFailed.value ? DEFAULT_AVATARS[props.kind] : props.src,
)
const radiusStyle = computed(() => (props.round ? '50%' : `${props.radius}px`))
</script>

<template>
  <span
    class="base-avatar"
    :class="{ 'base-avatar--bordered': bordered }"
    :style="{ width: `${size}px`, height: `${size}px`, borderRadius: radiusStyle }"
    :aria-hidden="name ? undefined : 'true'"
  >
    <img
      :src="effectiveSrc"
      :alt="name ?? ''"
      class="base-avatar__img"
      decoding="async"
      @error="loadFailed = true"
    />
  </span>
</template>

<style scoped>
/* 默认 SVG 为透明底：底色取主题令牌，明暗模式自动适配 */
.base-avatar {
  display: inline-block;
  flex-shrink: 0;
  overflow: hidden;
  background: var(--app-muted-bg);
  vertical-align: middle;
}
.base-avatar--bordered {
  border: 1px solid var(--app-border);
}
.base-avatar__img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
