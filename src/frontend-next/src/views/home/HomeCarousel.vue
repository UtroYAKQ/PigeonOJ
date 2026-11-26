<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useIntervalFn } from '@vueuse/core'
import { useI18n } from 'vue-i18n'

import type { SiteBanner } from '@/types'

const props = withDefaults(defineProps<{ banners: SiteBanner[]; interval?: number }>(), {
  interval: 5000,
})

const emit = defineEmits<{ open: [banner: SiteBanner] }>()
const { t } = useI18n()

const current = ref(0)
const count = computed(() => props.banners.length)
/** 已经加载过的图片保持挂载，避免切回时重新解码导致空窗 */
const loaded = ref(new Set<number>())

const { pause, resume } = useIntervalFn(
  () => {
    if (count.value > 1) current.value = (current.value + 1) % count.value
  },
  () => props.interval,
  { immediate: count.value > 1 },
)

/** 手动切图后重新计时，避免刚点完圆点立刻又自动跳一张 */
function restart(): void {
  if (count.value <= 1) return
  pause()
  resume()
}

watch(
  () => props.banners.length,
  (length) => {
    current.value = 0
    loaded.value.clear()
    if (length > 1) resume()
    else pause()
  },
  { immediate: true },
)

/** 首次只解码当前与相邻海报；加载过的保留挂载，切回不会闪空白 */
function shouldLoad(index: number): boolean {
  if (count.value <= 2 || loaded.value.has(index)) return true
  const diff = Math.abs(index - current.value)
  return diff === 0 || diff === 1 || diff === count.value - 1
}

function markLoaded(index: number): void {
  loaded.value.add(index)
}

function select(index: number): void {
  current.value = index
  restart()
}
</script>

<template>
  <div
    class="group relative h-full w-full overflow-hidden rounded-xl border border-border bg-surface"
  >
    <template v-for="(banner, index) in banners" :key="index">
      <Transition name="carousel-fade">
        <div
          v-show="index === current"
          class="absolute inset-0"
          :style="{ zIndex: index === current ? 2 : 1 }"
        >
          <component
            :is="banner.link ? 'button' : 'div'"
            :type="banner.link ? 'button' : undefined"
            class="relative block h-full w-full overflow-hidden text-left"
            :class="banner.link ? 'cursor-pointer' : 'cursor-default'"
            :aria-label="banner.title || undefined"
            @click="banner.link && emit('open', banner)"
          >
            <img
              v-if="shouldLoad(index)"
              :src="banner.image"
              :alt="banner.title"
              class="h-full w-full object-cover"
              decoding="async"
              @load="markLoaded(index)"
            />
            <div
              v-if="banner.title"
              class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent px-5 pb-4 pt-12 text-[14px] font-semibold text-white"
            >
              {{ banner.title }}
            </div>
          </component>
        </div>
      </Transition>
    </template>

    <template v-if="count > 1">
      <div class="absolute bottom-3 left-1/2 z-10 flex -translate-x-1/2 items-center gap-1.5">
        <button
          v-for="(_, index) in banners"
          :key="`dot-${index}`"
          type="button"
          class="size-1.5 rounded-full transition-all"
          :class="index === current ? 'w-4 bg-white' : 'bg-white/50 hover:bg-white/80'"
          :aria-label="t('home.slideIndex', { index: index + 1 })"
          @click.stop="select(index)"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
/* 交叉淡入淡出：新图在上层淡入，旧图下层淡出，避免瞬切与空窗 */
.carousel-fade-enter-active,
.carousel-fade-leave-active {
  transition: opacity 420ms ease;
}
.carousel-fade-enter-from,
.carousel-fade-leave-to {
  opacity: 0;
}
</style>
