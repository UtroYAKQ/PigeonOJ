<script setup lang="ts">
import { computed } from 'vue'

import defaultContestAvatar from '@/assets/avatars/default-contest.svg'
import defaultTeamAvatar from '@/assets/avatars/default-team.svg'
import defaultUserAvatar from '@/assets/avatars/default-user.svg'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'

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

const radiusStyle = computed(() => (props.round ? undefined : `${props.radius}px`))
</script>

<template>
  <Avatar
    :shape="round ? 'circle' : 'square'"
    class="align-middle"
    :class="{ 'border border-border': bordered }"
    :style="{ width: `${size}px`, height: `${size}px`, borderRadius: radiusStyle }"
    :aria-hidden="name ? undefined : 'true'"
  >
    <AvatarImage
      v-if="src"
      :src="src"
      :alt="name ?? ''"
      class="size-full object-cover"
    />
    <AvatarFallback class="size-full">
      <img :src="DEFAULT_AVATARS[kind]" alt="" class="size-full object-cover" />
    </AvatarFallback>
  </Avatar>
</template>
