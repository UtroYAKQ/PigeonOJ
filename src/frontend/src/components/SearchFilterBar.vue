<script setup lang="ts">
import { Search as SearchIcon } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'

// showSearch 必须显式给默认值 true：Boolean prop 缺省时会被 Vue 强转为 false（而非 undefined），
// 「未传 = 显示」的语义必须经 withDefaults 落实，否则搜索输入框永远不渲染
withDefaults(
  defineProps<{
    /** 搜索关键词 v-model */
    keyword?: string
    /** 搜索框占位文案 */
    placeholder?: string
    /** 搜索框宽度（默认 240px） */
    searchWidth?: string
    /** 是否显示搜索框与查询按钮（默认 true） */
    showSearch?: boolean
  }>(),
  { searchWidth: '240px', showSearch: true },
)

const emit = defineEmits<{
  'update:keyword': [value: string]
  search: []
  reset: []
}>()

const { t } = useI18n()

// 搜索统一手动触发（docs/frontend.md「表格工作台」）：输入只同步关键词，
// 点击「查询」或回车才发起；清空（X）立即按空关键词重查
</script>

<template>
  <div class="search-filter-bar">
    <n-input
      v-if="showSearch"
      :value="keyword"
      clearable
      class="search-filter-bar__search"
      :style="{ width: searchWidth }"
      :placeholder="placeholder"
      @input="(v: string) => emit('update:keyword', v)"
      @keyup.enter="$emit('search')"
      @clear="$emit('reset')"
    >
      <template #prefix>
        <n-icon size="15"><SearchIcon /></n-icon>
      </template>
    </n-input>
    <!-- 查询作用于全部条件，按钮置于筛选组末尾收尾（而非插在关键词后） -->
    <slot />
    <n-button v-if="showSearch" type="primary" @click="$emit('search')">
      {{ t('action.search') }}
    </n-button>
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
