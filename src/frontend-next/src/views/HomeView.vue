<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  ArrowRight,
  ChevronRight,
  Library,
  Lightbulb,
  Megaphone,
  Sparkles,
  Trophy,
  Users,
  Files,
} from '@lucide/vue'

import MarkdownView from '@/components/common/MarkdownView.vue'
import { TONE_SURFACE_CLASSES } from '@/components/common/tone'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import BrandMark from '@/layout/BrandMark.vue'
import HomeCarousel from '@/views/home/HomeCarousel.vue'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import type { SiteBanner } from '@/types'

const router = useRouter()
const { t } = useI18n()
const appStore = useAppStore()
const userStore = useUserStore()

const banners = computed<SiteBanner[]>(() =>
  (appStore.siteConfig.banners ?? []).filter((b) => !!b.image),
)
const announcement = computed(() => (appStore.siteConfig.announcement ?? '').trim())

/** 快捷入口按语义色区分，颜色仅承担识别作用 */
const cards = [
  {
    titleKey: 'nav.problems',
    descKey: 'home.problems',
    to: '/problems',
    icon: Library,
    tone: 'primary',
  },
  {
    titleKey: 'nav.problemSets',
    descKey: 'home.problemSets',
    to: '/problem-sets',
    icon: Files,
    tone: 'info',
  },
  {
    titleKey: 'nav.contests',
    descKey: 'home.contests',
    to: '/contests',
    icon: Trophy,
    tone: 'warning',
  },
  { titleKey: 'nav.teams', descKey: 'home.teams', to: '/teams', icon: Users, tone: 'success' },
] as const

const TIP_COUNT = 10
const tipIndex = ref(Math.floor(Math.random() * TIP_COUNT))
const tipText = computed(() => t(`home.tips.t${tipIndex.value + 1}`))

function nextTip(): void {
  let next = Math.floor(Math.random() * TIP_COUNT)
  if (next === tipIndex.value) next = (next + 1) % TIP_COUNT
  tipIndex.value = next
}

function openBanner(banner: SiteBanner): void {
  if (banner.link) router.push(banner.link)
}
</script>

<template>
  <div
    class="mx-auto flex w-full max-w-[1920px] flex-col px-4 pb-6 pt-4 sm:px-6 lg:min-h-full"
  >
    <header
      v-if="!userStore.isLoggedIn"
      class="mb-4 flex shrink-0 flex-wrap justify-end gap-3 lg:mb-5"
    >
      <Button variant="outline" size="sm" @click="router.push('/login')">
        {{ t('user.login') }}
      </Button>
      <Button size="sm" @click="router.push('/register')">
        {{ t('home.createAccount') }}
        <ArrowRight class="size-4" />
      </Button>
    </header>

<!-- 主视觉：左轮播海报（2fr）+ 右系统公告（1fr），两列高度由左列内容决定 -->
    <div class="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
      <div class="min-w-0">
        <div
          v-if="banners.length"
          class="aspect-video lg:aspect-auto lg:h-[clamp(320px,46vh,520px)]"
        >
          <HomeCarousel :banners="banners" @open="openBanner" />
        </div>
        <div
          v-else
          class="relative flex min-h-[clamp(280px,42vh,420px)] flex-col justify-center overflow-hidden rounded-xl border border-border bg-surface px-8 py-10 sm:px-12"
        >
          <div class="dot-grid pointer-events-none absolute inset-0 opacity-40" />
          <div
            class="pointer-events-none absolute -right-32 -top-40 size-[480px] rounded-full bg-brand-soft blur-3xl"
          />
          <div class="relative max-w-[40ch]">
            <div class="flex items-center gap-3">
              <BrandMark />
              <span class="text-[13px] font-semibold tracking-[0.18em] text-muted-foreground">
                {{ appStore.siteName }}
              </span>
            </div>
            <h2
              class="mt-6 text-balance text-[clamp(22px,3.8vw,56px)] font-semibold leading-[1.15] tracking-tight"
            >
              {{ t('home.intro') }}
            </h2>
            <Button class="mt-8" @click="router.push('/problems')">
              {{ t('home.explore') }}
              <ArrowRight class="size-4" />
            </Button>
          </div>
        </div>
      </div>

      <div class="relative min-h-[280px] lg:min-h-0">
        <Card class="flex h-full flex-col overflow-hidden lg:absolute lg:inset-0 lg:h-auto">
          <header class="flex shrink-0 items-center gap-2.5 border-b border-border px-5 py-4">
            <Megaphone class="size-[18px] text-brand" />
            <h2 class="text-[15px] font-semibold">{{ t('home.announcement') }}</h2>
          </header>
          <div class="min-h-0 flex-1 overflow-auto px-5 py-4">
            <MarkdownView v-if="announcement" :source="announcement" />
            <p v-else class="text-[13px] text-muted-foreground">{{ t('home.noAnnouncement') }}</p>
          </div>
        </Card>
      </div>
    </div>


    <!-- 下方区块吃满剩余高度：入口磁贴 + 小贴士不再挤在窄栏里 -->
    <div class="mt-4 flex flex-col gap-4">
      <section
        class="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4"
        :aria-label="t('home.explore')"
      >
        <Card
          v-for="card in cards"
          :key="card.to"
          class="group min-h-[88px] overflow-hidden transition-colors hover:border-foreground/20"
        >
          <button
            type="button"
            class="flex h-full w-full items-center gap-4 px-5 py-5 text-left sm:px-6"
            @click="router.push(card.to)"
          >
            <span
              class="grid size-12 shrink-0 place-items-center rounded-xl"
              :class="TONE_SURFACE_CLASSES[card.tone]"
            >
              <component :is="card.icon" class="size-5" :stroke-width="1.8" />
            </span>
            <span class="min-w-0 flex-1">
              <span class="block text-[17px] font-semibold">{{ t(card.titleKey) }}</span>
              <span class="mt-1 block truncate text-[13px] text-muted-foreground">
                {{ t(card.descKey) }}
              </span>
            </span>
            <ChevronRight
              class="size-5 shrink-0 text-muted-foreground/60 transition-transform group-hover:translate-x-0.5"
            />
          </button>
        </Card>
      </section>

      <Card
        class="flex min-h-[136px] flex-col px-6 py-5"
        :aria-label="t('home.tipsLabel')"
      >
        <header class="flex shrink-0 items-center gap-2.5">
          <Lightbulb class="size-[18px] text-brand" />
          <h2 class="text-[15px] font-semibold">{{ t('home.tipsLabel') }}</h2>
          <Button
            variant="ghost"
            size="xs"
            class="ml-auto text-[12px] text-muted-foreground"
            @click="nextTip"
          >
            <Sparkles class="size-3.5" />
            {{ t('home.nextTip') }}
          </Button>
        </header>
        <Transition name="tip-fade" mode="out-in">
          <p :key="tipIndex" class="mt-3 text-[15px] leading-8 text-foreground/80">
            {{ tipText }}
          </p>
        </Transition>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.tip-fade-enter-active,
.tip-fade-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}
.tip-fade-enter-from {
  opacity: 0;
  transform: translateX(6px);
}
.tip-fade-leave-to {
  opacity: 0;
  transform: translateX(-6px);
}
</style>
