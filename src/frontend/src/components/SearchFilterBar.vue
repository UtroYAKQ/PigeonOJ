<script setup lang="ts">
import { Search as SearchIcon } from '@element-plus/icons-vue'
import { ref } from 'vue'

defineProps<{
  /** 搜索关键词 v-model */
  keyword?: string
  /** 搜索框占位文案 */
  placeholder?: string
  /** 搜索框宽度（默认 240px） */
  searchWidth?: string
  /** 是否显示搜索框（默认 true） */
  showSearch?: boolean
}>()

const emit = defineEmits<{
  'update:keyword': [value: string]
  search: []
  reset: []
}>()

// 中文输入法组词过程不触发搜索（compositionend 后再统一触发）
const composing = ref(false)
let searchTimer: number | undefined

function scheduleSearch() {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => emit('search'), 300)
}
function onCompositionStart() {
  composing.value = true
}
function onCompositionEnd() {
  composing.value = false
  scheduleSearch()
}
function onInput(value: string) {
  emit('update:keyword', value)
  if (!composing.value) scheduleSearch()
}
</script>

<template>
  <div class="search-filter-bar">
    <n-input
      v-if="showSearch !== false"
      :value="keyword"
      clearable
      class="search-filter-bar__search"
      :style="{ width: searchWidth ?? '240px' }"
      :placeholder="placeholder"
      @input="onInput"
      @compositionstart="onCompositionStart"
      @compositionend="onCompositionEnd"
      @keyup.enter="$emit('search')"
      @clear="$emit('reset')"
    >
      <template #prefix>
        <n-icon size="15"><SearchIcon /></n-icon>
      </template>
    </n-input>
    <slot />
    <div class="search-filter-bar__spacer" />
    <slot name="actions" />
  </div>
</template>

<style scoped>
.search-filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}
.search-filter-bar__search {
  min-width: 0;
}
.search-filter-bar__spacer {
  flex: 1;
}
</style>
