import { useEventListener, useMediaQuery } from '@vueuse/core'
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const SPLIT_KEY = 'pigeonoj.problems.splitRatio'

function loadRatio(): number {
  const raw = Number(localStorage.getItem(SPLIT_KEY))
  return Number.isFinite(raw) && raw >= 0.25 && raw <= 0.75 ? raw : 0.5
}

/**
 * 可拖拽分栏 composable（桌面端左右独立滚动，比例持久化；窄屏自动上下堆叠）。
 * 从 ProblemDetailView.vue 提取，供需要分栏的页面复用。
 */
export function useSplitPane() {
  // 窄屏（<900px）自动上下堆叠；断点监听由 useMediaQuery 接管（卸载自动清理）
  const isDesktop = useMediaQuery('(min-width: 900px)')
  const splitRef = ref<HTMLElement>()
  const ratio = ref(loadRatio())
  const splitHeight = ref('')

  let resizing = false

  function startResize(event: PointerEvent) {
    if (!isDesktop.value) return
    event.preventDefault()
    resizing = true
    document.body.classList.add('is-splitting')
  }

  function onPointerMove(event: PointerEvent) {
    if (!resizing || !splitRef.value) return
    const rect = splitRef.value.getBoundingClientRect()
    ratio.value = Math.min(0.75, Math.max(0.25, (event.clientX - rect.left) / rect.width))
  }

  function endResize() {
    if (!resizing) return
    resizing = false
    document.body.classList.remove('is-splitting')
    localStorage.setItem(SPLIT_KEY, String(ratio.value))
  }

  function resetSplit() {
    ratio.value = 0.5
    localStorage.setItem(SPLIT_KEY, String(ratio.value))
  }

  function updateSplitHeight() {
    if (!isDesktop.value) {
      splitHeight.value = ''
      return
    }
    const el = splitRef.value
    const scroller = el?.closest('.app-main') as HTMLElement | null
    if (!el || !scroller) {
      splitHeight.value = ''
      return
    }
    const styles = getComputedStyle(scroller)
    const padTop = parseFloat(styles.paddingTop) || 0
    const padBottom = parseFloat(styles.paddingBottom) || 0
    const topGap =
      el.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - padTop
    const height = Math.max(420, Math.floor(scroller.clientHeight - padTop - padBottom - topGap) - 1)
    splitHeight.value = `${height}px`
  }

  const layoutStyle = computed(() =>
    isDesktop.value
      ? ({ '--split': `${ratio.value * 100}%`, height: splitHeight.value || undefined } as Record<
          string,
          string | undefined
        >)
      : {},
  )

  // 拖拽 / 窗口尺寸 / 语言切换事件统一交给 useEventListener：组件卸载自动解绑；
  // pointermove / pointerup 常驻但由 resizing 标志守卫，等价于原先的动态挂载
  useEventListener(window, 'pointermove', onPointerMove)
  useEventListener(window, 'pointerup', endResize)
  useEventListener(window, 'resize', updateSplitHeight)
  useEventListener(window, 'pigeonoj:locale-change', updateSplitHeight)
  watch(isDesktop, updateSplitHeight)

  // 卸载兜底：拖拽中途离开页面时移除拖拽态样式（正常路径由 endResize 移除）
  onBeforeUnmount(() => {
    document.body.classList.remove('is-splitting')
  })

  return {
    isDesktop,
    splitRef,
    ratio,
    layoutStyle,
    startResize,
    resetSplit,
    updateSplitHeight,
  }
}
