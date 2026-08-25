import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

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
  const desktopQuery = window.matchMedia('(min-width: 900px)')
  const isDesktop = ref(desktopQuery.matches)
  const splitRef = ref<HTMLElement>()
  const ratio = ref(loadRatio())
  const splitHeight = ref('')

  let resizing = false

  function startResize(event: PointerEvent) {
    if (!isDesktop.value) return
    event.preventDefault()
    resizing = true
    document.body.classList.add('is-splitting')
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', endResize)
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
    window.removeEventListener('pointermove', onPointerMove)
    window.removeEventListener('pointerup', endResize)
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

  function onDesktopChange(event: MediaQueryListEvent) {
    isDesktop.value = event.matches
    updateSplitHeight()
  }

  const layoutStyle = computed(() =>
    isDesktop.value
      ? ({ '--split': `${ratio.value * 100}%`, height: splitHeight.value || undefined } as Record<
          string,
          string | undefined
        >)
      : {},
  )

  onMounted(() => {
    desktopQuery.addEventListener('change', onDesktopChange)
    window.addEventListener('resize', updateSplitHeight)
    window.addEventListener('pigeonoj:locale-change', updateSplitHeight)
  })

  onBeforeUnmount(() => {
    desktopQuery.removeEventListener('change', onDesktopChange)
    window.removeEventListener('resize', updateSplitHeight)
    window.removeEventListener('pigeonoj:locale-change', updateSplitHeight)
    document.body.classList.remove('is-splitting')
    window.removeEventListener('pointermove', onPointerMove)
    window.removeEventListener('pointerup', endResize)
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
