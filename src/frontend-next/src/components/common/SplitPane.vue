<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useEventListener, useMediaQuery } from '@vueuse/core'

const props = withDefaults(
  defineProps<{
    storageKey?: string
    min?: number
    max?: number
  }>(),
  { storageKey: 'pigeonoj.split.ratio', min: 0.25, max: 0.75 },
)

const isDesktop = useMediaQuery('(min-width: 900px)')
const root = ref<HTMLElement>()
const ratio = ref(loadRatio())
let resizing = false

/** 拖到接近端点时吸附：0 = 只显示右侧（编辑器），1 = 只显示左侧（题面） */
const SNAP_THRESHOLD = 0.03

function loadRatio(): number {
  const raw = Number(localStorage.getItem(props.storageKey))
  return Number.isFinite(raw) && raw >= props.min && raw <= props.max ? raw : 0.5
}

function startResize(event: PointerEvent): void {
  if (!isDesktop.value) return
  event.preventDefault()
  resizing = true
  document.body.classList.add('is-splitting')
}

function onPointerMove(event: PointerEvent): void {
  if (!resizing || !root.value) return
  const rect = root.value.getBoundingClientRect()
  let next = Math.min(props.max, Math.max(props.min, (event.clientX - rect.left) / rect.width))
  if (next <= SNAP_THRESHOLD && props.min === 0) next = 0
  else if (next >= 1 - SNAP_THRESHOLD && props.max === 1) next = 1
  ratio.value = next
}

function endResize(): void {
  if (!resizing) return
  resizing = false
  document.body.classList.remove('is-splitting')
  localStorage.setItem(props.storageKey, String(ratio.value))
}

function reset(): void {
  ratio.value = 0.5
  localStorage.setItem(props.storageKey, '0.5')
}

const gridStyle = computed(() => {
  if (!isDesktop.value) return {}
  const ratioPercent = ratio.value * 100
  return {
    gridTemplateColumns: `calc(${ratioPercent}% - ${ratio.value * 12}px) 12px minmax(0, 1fr)`,
  }
})

useEventListener(window, 'pointermove', onPointerMove)
useEventListener(window, 'pointerup', endResize)
onBeforeUnmount(() => document.body.classList.remove('is-splitting'))
</script>

<template>
  <div
    ref="root"
    class="block min-[900px]:grid min-[900px]:h-full min-[900px]:items-stretch"
    :style="gridStyle"
  >
    <section class="min-h-0 min-w-0 min-[900px]:overflow-y-auto min-[900px]:pr-1">
      <slot name="left" />
    </section>

    <div
      v-if="isDesktop"
      class="group flex cursor-col-resize touch-none items-center justify-center"
      role="separator"
      aria-orientation="vertical"
      @pointerdown="startResize"
      @dblclick="reset"
    >
      <div class="h-14 w-1 rounded-full bg-border transition-colors group-hover:bg-brand" />
    </div>

    <section
      class="mt-4 min-h-0 min-w-0 min-[900px]:mt-0 min-[900px]:overflow-hidden min-[900px]:pl-2"
    >
      <slot name="right" />
    </section>
  </div>
</template>
