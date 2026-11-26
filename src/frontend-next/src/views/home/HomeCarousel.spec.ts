import { createApp, defineComponent, h, nextTick, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@lucide/vue', () => ({
  ChevronLeft: { template: '<span />' },
  ChevronRight: { template: '<span />' },
}))
vi.mock('@/components/ui/button', () => ({
  Button: {
    template: '<button type="button" @click="$emit(\'click\', $event)"><slot /></button>',
    emits: ['click'],
  },
}))

import HomeCarousel from './HomeCarousel.vue'
import type { SiteBanner } from '@/types'

const banners = (count: number): SiteBanner[] =>
  Array.from({ length: count }, (_, i) => ({
    title: `banner-${i}`,
    image: `/b${i}.png`,
    link: '',
  }))

function mountCarousel(items: ReturnType<typeof banners>) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = createApp(HomeCarousel, { banners: items })
  app.mount(host)
  return {
    host,
    unmount: () => {
      app.unmount()
      host.remove()
    },
  }
}

function visibleTitle(host: HTMLElement): string | null {
  const slides = [...host.querySelectorAll('[aria-label^="banner-"]')]
  const active = slides.find((slide) => (slide.parentElement as HTMLElement).style.zIndex === '2')
  return active?.getAttribute('aria-label') ?? null
}

function mountAsyncCarousel() {
  const items = ref<ReturnType<typeof banners>>([])
  const host = document.createElement('div')
  document.body.appendChild(host)
  const wrapper = defineComponent({ render: () => h(HomeCarousel, { banners: items.value }) })
  const app = createApp(wrapper)
  app.mount(host)
  return {
    host,
    items,
    unmount: () => {
      app.unmount()
      host.remove()
    },
  }
}

describe('HomeCarousel', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('海报异步加载后自动轮播仍能启动', async () => {
    const { host, items, unmount } = mountAsyncCarousel()
    vi.advanceTimersByTime(20000)
    await nextTick()
    expect(visibleTitle(host)).toBeNull()

    items.value = banners(3)
    await nextTick()
    vi.advanceTimersByTime(5000)
    await nextTick()
    expect(visibleTitle(host)).toBe('banner-1')
    unmount()
  })

  it('鼠标悬停不再中断自动轮播', async () => {
    const { host, unmount } = mountCarousel(banners(3))
    const root = host.firstElementChild as HTMLElement

    root.dispatchEvent(new MouseEvent('mouseenter'))
    vi.advanceTimersByTime(5000)
    await nextTick()
    expect(visibleTitle(host)).toBe('banner-1')
    unmount()
  })

  it('不渲染左右箭头，只保留底部圆点', () => {
    const { host, unmount } = mountCarousel(banners(3))
    expect(host.querySelector('[aria-label="home.prevSlide"]')).toBeNull()
    expect(host.querySelector('[aria-label="home.nextSlide"]')).toBeNull()
    expect(host.querySelectorAll('[aria-label^="home.slideIndex"]')).toHaveLength(3)
    unmount()
  })

  it('底部圆点可切换，且切换后重新计时', async () => {
    const { host, unmount } = mountCarousel(banners(3))
    const dots = host.querySelectorAll('[aria-label^="home.slideIndex"]')

    vi.advanceTimersByTime(4000)
    ;(dots[2] as HTMLButtonElement).click()
    await nextTick()
    expect(visibleTitle(host)).toBe('banner-2')

    vi.advanceTimersByTime(4000)
    await nextTick()
    expect(visibleTitle(host)).toBe('banner-2')

    vi.advanceTimersByTime(1000)
    await nextTick()
    expect(visibleTitle(host)).toBe('banner-0')
    unmount()
  })

  it('自动轮播会按间隔切换到下一张', async () => {
    const { host, unmount } = mountCarousel(banners(3))
    expect(visibleTitle(host)).toBe('banner-0')
    vi.advanceTimersByTime(5000)
    await nextTick()
    expect(visibleTitle(host)).toBe('banner-1')
    unmount()
  })
})
