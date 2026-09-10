<script setup lang="ts">
/**
 * 首页：WizardShell 页眉卡片壳（标题 = 时段问候 / 欢迎语，动作区 = 访客注册 / 登录）。
 * 主视觉区左轮播海报（site.banners，n-carousel）、右系统公告（site.announcement，
 * Markdown 经 MarkdownView 渲染：html:false + DOMPurify 白名单，与比赛公告同链路），
 * 下方快捷入口磁贴（题库 / 题单 / 比赛 / 团队）与算法小贴士栏（随机换一条）。
 * 内容全部由公开站点配置驱动，未配置海报时左侧回退品牌横幅（不空窗），
 * 未配置公告时右侧弱化占位。
 * 性能：海报图最大 5MB 不受控，轮播仅挂载「当前 + 相邻」slide 的 src（其余懒加载），
 * 避免一次性解码全部大图导致掉帧；loop 复制的首尾副本与真身共用 banner 序号判定。
 */
import {
  ArrowRight,
  Collection,
  Document,
  Opportunity,
  Trophy,
  UserFilled,
} from '@element-plus/icons-vue'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import MarkdownView from '@/components/MarkdownView.vue'
import WizardShell from '@/components/WizardShell.vue'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import type { SiteBanner } from '@/types'

const router = useRouter()
const appStore = useAppStore()
const userStore = useUserStore()
const { t } = useI18n()

const siteName = computed(() => appStore.siteConfig.name || 'PigeonOJ')

/** 时段问候（登录用户）；访客展示站点欢迎语 */
const greeting = computed(() => {
  if (!userStore.isLoggedIn) return t('home.welcome', { name: siteName.value })
  const hour = new Date().getHours()
  const key =
    hour < 6
      ? 'dawn'
      : hour < 12
        ? 'morning'
        : hour < 14
          ? 'noon'
          : hour < 18
            ? 'afternoon'
            : 'evening'
  return t('home.greeting', {
    greet: t(`home.${key}`),
    name: userStore.user?.nickname ?? t('home.student'),
  })
})

const banners = computed<SiteBanner[]>(() =>
  (appStore.siteConfig.banners ?? []).filter((b) => !!b.image),
)
const announcement = computed(() => (appStore.siteConfig.announcement ?? '').trim())

/**
 * 轮播懒加载：用 CarouselItem 插槽参数（isActive/isPrev/isNext）判断是否挂真实 src。
 * 仅「当前 + 前后相邻」加载：autoplay 推进前下一张已提前挂载预载，切换不空窗；
 * 其余 slide 渲染无 src 的 <img>，不发起请求也不解码，避免 10 张大图一次性全解。
 * 无需记录「已加载」状态：src 移除后浏览器已有缓存（immutable），再切入瞬时恢复。
 * 注意：单张 banner 时 naive 内部 realIndex(+1 偏移) 与未复制的轨道对不上，
 * isActive/isPrev/isNext 恒为 false（naive 的 --current 类同样失效，仅对滑动无感），
 * 故单张退化为静态 banner，不做门控直接挂图。
 */

const cards = [
  {
    titleKey: 'nav.problems',
    descKey: 'home.problems',
    to: '/problems',
    icon: Collection,
    tone: 'primary',
  },
  {
    titleKey: 'nav.problemSets',
    descKey: 'home.problemSets',
    to: '/problem-sets',
    icon: Document,
    tone: 'info',
  },
  {
    titleKey: 'nav.contests',
    descKey: 'home.contests',
    to: '/contests',
    icon: Trophy,
    tone: 'warning',
  },
  {
    titleKey: 'nav.teams',
    descKey: 'home.teams',
    to: '/teams',
    icon: UserFilled,
    tone: 'success',
  },
]

/* ---- 算法小贴士：i18n 键 home.tips.t1..t10 随机抽一条，「换一条」重抽（不与当前重复） ---- */
const TIP_COUNT = 10
const tipIndex = ref(Math.floor(Math.random() * TIP_COUNT))
const tipText = computed(() => t(`home.tips.t${tipIndex.value + 1}`))
function nextTip() {
  let next = Math.floor(Math.random() * TIP_COUNT)
  if (next === tipIndex.value) next = (next + 1) % TIP_COUNT
  tipIndex.value = next
}

function openBanner(banner: SiteBanner) {
  if (banner.link) router.push(banner.link)
}
</script>

<template>
  <WizardShell :title="greeting" class="home page-fill">
    <template #actions>
      <!-- 访客：注册 / 登录；登录用户：动作区留空 -->
      <template v-if="!userStore.isLoggedIn">
        <n-button type="primary" @click="router.push('/register')">
          {{ t('home.createAccount') }}
          <n-icon class="home__arrow" :component="ArrowRight" />
        </n-button>
        <n-button secondary @click="router.push('/login')">{{ t('user.login') }}</n-button>
      </template>
    </template>

    <!-- 主视觉：左轮播海报（2fr）+ 右系统公告（1fr） -->
    <div class="home__top">
      <div class="home__panel home__panel--carousel">
        <!-- 海报：1 张时退化为静态 banner（不显示圆点）；未配置时品牌横幅兜底 -->
        <n-carousel
          v-if="banners.length"
          :show-arrow="banners.length > 1"
          :show-dots="banners.length > 1"
          :autoplay="banners.length > 1"
          :interval="5000"
          draggable
          class="home__carousel"
        >
          <!-- 多张：仅当前 + 相邻 slide 挂真实 src（懒加载，见脚本注释）；单张：静态直挂 -->
          <n-carousel-item v-for="(banner, index) in banners" :key="index">
            <template #default="{ isActive, isPrev, isNext }">
              <component
                :is="banner.link ? 'button' : 'div'"
                type="button"
                class="home__slide"
                :class="{ 'home__slide--link': banner.link }"
                :aria-label="banner.title || undefined"
                @click="openBanner(banner)"
              >
                <img
                  v-if="banners.length === 1 || isActive || isPrev || isNext"
                  :src="banner.image"
                  :alt="banner.title"
                  class="home__slide-img"
                  decoding="async"
                />
                <div v-if="banner.title" class="home__slide-caption">
                  <span>{{ banner.title }}</span>
                </div>
              </component>
            </template>
          </n-carousel-item>
        </n-carousel>
        <div v-else class="home__brand">
          <p class="home__kicker">{{ siteName }}</p>
          <h1 class="home__brand-title">{{ t('home.intro') }}</h1>
          <div class="home__brand-actions">
            <n-button type="primary" @click="router.push('/problems')">
              {{ t('home.explore') }}
              <n-icon class="home__arrow" :component="ArrowRight" />
            </n-button>
          </div>
        </div>
      </div>

      <div class="home__panel home__panel--announcement">
        <div class="home__panel-head">
          <span class="home__panel-title">{{ t('home.announcement') }}</span>
        </div>
        <div class="home__panel-body">
          <MarkdownView v-if="announcement" class="home__announcement" :source="announcement" />
          <p v-else class="home__notice--empty">{{ t('home.noAnnouncement') }}</p>
        </div>
      </div>
    </div>

    <!-- 快捷入口 + 小贴士：整体居中吸收主视觉缩放后的剩余空间 -->
    <div class="home__bottom">
      <!-- 快捷入口：紧凑磁贴，单行图标 + 标题 + 描述 -->
      <section class="home__tiles" :aria-label="t('home.explore')">
        <button
          v-for="card in cards"
          :key="card.to"
          type="button"
          class="tile"
          @click="router.push(card.to)"
        >
          <span class="tile__icon" :class="`tile__icon--${card.tone}`">
            <n-icon size="20" :component="card.icon" />
          </span>
          <span class="tile__text">
            <span class="tile__title">{{ t(card.titleKey) }}</span>
            <span class="tile__desc">{{ t(card.descKey) }}</span>
          </span>
          <n-icon class="tile__arrow" :component="ArrowRight" />
        </button>
      </section>

      <!-- 算法小贴士：白底大盒（标题 + 内容 + 换一条），随机一条可换 -->
      <section class="tip-box" :aria-label="t('home.tipsLabel')">
        <header class="tip-box__head">
          <span class="tip-box__icon" aria-hidden="true">
            <n-icon size="16" :component="Opportunity" />
          </span>
          <h2 class="tip-box__title">{{ t('home.tipsLabel') }}</h2>
          <n-button
            text
            type="primary"
            size="small"
            class="tip-box__next"
            :aria-label="t('home.nextTip')"
            @click="nextTip"
          >
            {{ t('home.nextTip') }}
          </n-button>
        </header>
        <Transition name="tip-fade" mode="out-in">
          <p :key="tipIndex" class="tip-box__text">{{ tipText }}</p>
        </Transition>
      </section>
    </div>
  </WizardShell>
</template>

<style scoped>
/* WizardShell 根即 n-card（.home 透传其上）：卡片已是 flex 列 + .page-fill 一屏，
   这里只打通内容层高度链（naive 卡片内容类名为单横杠 n-card-content） */
.home :deep(.n-card-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ---- 主视觉两栏：视口高度封顶，公告内部滚动 ---- */
.home__top {
  flex: none;
  height: clamp(330px, 50dvh, 550px);
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr);
  gap: 14px;
}
/* 底部区块（磁贴 + 小贴士）弹性分占剩余空间，铺满主视觉以下布局 */
.home__bottom {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.home__panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--app-border);
  border-radius: 3px;
}
.home__panel--carousel {
  background: var(--app-muted-bg);
}

/* 轮播：圆角贴设计系统，图片 cover 防拉伸。
   clip-path 内裁 1px：抵消相邻滑片亚像素取整渗色（边缘 1px 邻图细线），
   视觉边缘由面板自身 1px 边框承担。
   clip-path 放在 slide img（静态层）而非做 transform 过渡的 slides 轨道：
   动画容器带裁剪会放大合成/重绘开销 */
.home__carousel {
  flex: 1;
  min-height: 0;
  width: 100%;
}
.home__slide {
  position: relative;
  display: block;
  width: 100%;
  height: 100%;
  padding: 0;
  border: 0;
  background: var(--app-muted-bg);
  cursor: default;
  /* 点击 / 拖拽后浏览器默认 focus 光晕会包住图片形似彩色边框，予以去除 */
  -webkit-tap-highlight-color: transparent;
}
.home__slide:focus {
  outline: none;
}
/* 键盘导航仍保留可见焦点（主色描边内缩，避免被面板 overflow 裁剪） */
.home__slide:focus-visible {
  outline: 2px solid var(--app-primary);
  outline-offset: -2px;
}
.home__slide--link {
  cursor: pointer;
}
.home__slide-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  clip-path: inset(1px);
}
/* 底部渐变遮罩 + 标题（暗色模式同样可读） */
.home__slide-caption {
  position: absolute;
  inset-inline: 0;
  bottom: 0;
  padding: 28px 16px 12px;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.55));
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  text-align: left;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
}

/* ---- 品牌兜底横幅（未配置海报时） ---- */
.home__brand {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  padding: 28px;
  background:
    radial-gradient(
      60% 90% at 100% 0%,
      color-mix(in srgb, var(--app-primary) 7%, transparent) 0%,
      transparent 60%
    ),
    var(--app-muted-bg);
}
.home__kicker {
  margin: 0 0 8px;
  color: var(--app-primary);
  font-size: 13px;
  font-weight: 600;
}
.home__brand-title {
  margin: 0;
  max-width: 480px;
  font-size: clamp(18px, 2.2vw, 24px);
  line-height: 1.4;
}
.home__brand-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
}
.home__arrow {
  margin-left: 4px;
}

/* ---- 公告面板：自带头部（替代 n-card title），正文独立滚动 ---- */
.home__panel--announcement {
  background: var(--app-card-bg, #fff);
}
.home__panel-head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--app-border);
}
.home__panel-title {
  font-size: 14px;
  font-weight: 600;
}
.home__panel-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 14px 16px;
}
.home__notice--empty {
  color: var(--app-text-secondary);
  opacity: 0.7;
}

/* ---- 快捷入口：磁贴行等高拉伸占位（内容垂直居中） ---- */
.home__tiles {
  flex: 1.15;
  min-height: 140px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  grid-auto-rows: minmax(0, 1fr);
  gap: 12px;
}
.tile {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  text-align: left;
  border: 1px solid var(--app-border);
  border-radius: 3px;
  background: var(--app-card-bg, #fff);
  cursor: pointer;
  transition: border-color 0.15s ease;
}
.tile:hover {
  border-color: var(--app-text-muted);
}
.tile:hover .tile__title {
  color: var(--app-primary);
}
.tile:focus-visible {
  outline: 2px solid var(--app-primary);
  outline-offset: 2px;
}
.tile__icon {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  border-radius: 8px;
}
.tile__icon--primary {
  color: var(--app-primary);
  background: color-mix(in srgb, var(--app-primary) 9%, transparent);
}
.tile__icon--warning {
  color: var(--app-warning);
  background: color-mix(in srgb, var(--app-warning) 10%, transparent);
}
.tile__icon--success {
  color: var(--app-success);
  background: color-mix(in srgb, var(--app-success) 10%, transparent);
}
.tile__icon--info {
  color: var(--app-info);
  background: color-mix(in srgb, var(--app-info) 10%, transparent);
}
.tile__text {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.tile__title {
  font-size: 14px;
  font-weight: 650;
  color: var(--app-text);
  transition: color 0.15s ease;
}
.tile__desc {
  font-size: 12px;
  color: var(--app-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 箭头常态隐藏，悬停浮现于右侧（与磁贴的平面风格一致，不做位移） */
.tile__arrow {
  margin-left: auto;
  flex-shrink: 0;
  color: var(--app-text-secondary);
  opacity: 0;
  transition: opacity 0.15s ease;
}
.tile:hover .tile__arrow {
  opacity: 1;
}

/* ---- 算法小贴士：白底大盒（标题行 + 内容），与磁贴同一平面卡片语言 ---- */
.tip-box {
  flex: 1;
  min-height: 120px;
  display: flex;
  flex-direction: column;
  padding: 16px 20px;
  border: 1px solid var(--app-border);
  border-radius: 3px;
  background: var(--app-card-bg, #fff);
}
.tip-box__head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.tip-box__icon {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  color: var(--app-primary);
}
.tip-box__title {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-size: 14px;
  font-weight: 650;
  color: var(--app-text);
}
.tip-box__next {
  flex-shrink: 0;
}
/* 内容在剩余高度垂直居中，盒体拉伸时不悬空 */
.tip-box__text {
  flex: 1;
  display: flex;
  align-items: center;
  margin: 8px 0 0;
  color: var(--app-text);
  font-size: 13px;
  line-height: 1.75;
}
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

@media (max-width: 860px) {
  /* 窄屏：主视觉与底部区块均为自然高度，整页滚动 */
  .home.page-fill {
    min-height: 0;
  }
  .home__top {
    height: auto;
    grid-template-columns: 1fr;
  }
  .home__bottom {
    flex: none;
  }
  .home__panel--carousel {
    min-height: 200px;
  }
  .home__tiles {
    flex: none;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-auto-rows: minmax(110px, auto);
  }
  .tip-box {
    flex: none;
  }
  .tip-box__text {
    flex: none;
    display: block;
  }
}
@media (max-width: 520px) {
  .home__tiles {
    grid-template-columns: 1fr;
  }
}
</style>
