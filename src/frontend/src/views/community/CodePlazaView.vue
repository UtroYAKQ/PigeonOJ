<script setup lang="ts">
/**
 * 代码广场（docs/contracts/community.md「代码广场」）：小卡片网格 + 关键词 / 语言筛选，
 * 点击卡片进入详情页查看代码；分享不关联题目、不设评论。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { listCodeShares } from '@/api/community'
import BaseAvatar from '@/components/BaseAvatar.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { usePagination } from '@/composables/usePagination'
import { languageOptions } from '@/constants/languages'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { CodeShareSummary } from '@/types'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const list = ref<CodeShareSummary[]>([])
const listLoading = ref(false)
const query = reactive({ keyword: '', language: null as string | null, mine: false })
const paging = usePagination({ defaultPageSize: 12 })

const languageFilterOptions = computed(() => [
  { label: t('codes.allLanguages'), value: '' },
  ...languageOptions.map((o) => ({ label: o.label, value: o.value })),
])

async function load() {
  const seq = paging.beginLoad()
  listLoading.value = true
  try {
    const res = await listCodeShares({
      page: paging.page.value,
      page_size: paging.pageSize.value,
      keyword: query.keyword || undefined,
      language: (query.language || undefined) as undefined,
      mine: query.mine || undefined,
    })
    if (!paging.isCurrent(seq)) return
    list.value = res.items
    paging.total.value = res.total
  } catch (e) {
    if (!paging.isCurrent(seq)) return
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    if (paging.isCurrent(seq)) listLoading.value = false
  }
}

function onSearch() {
  paging.resetPage()
  load()
}

function languageLabel(value: string) {
  return languageOptions.find((o) => o.value === value)?.label ?? value
}

function openShare(row: CodeShareSummary) {
  void router.push(`/codes/${row.id}`)
}

function writeShare() {
  void router.push('/codes/new')
}

onMounted(load)
</script>

<template>
  <WorkbenchShell>
    <SearchFilterBar
      :keyword="query.keyword"
      :placeholder="t('codes.searchPlaceholder')"
      @update:keyword="
        (v: string) => {
          query.keyword = v
        }
      "
      @search="onSearch"
      @reset="onSearch"
    >
      <n-select
        v-model:value="query.language"
        clearable
        style="width: 150px"
        :options="languageFilterOptions"
        :placeholder="t('codes.allLanguages')"
        @update:value="onSearch"
      />
      <n-checkbox
        :checked="query.mine"
        @update:checked="
          (v: boolean) => {
            query.mine = v
            onSearch()
          }
        "
      >
        {{ t('codes.mineOnly') }}
      </n-checkbox>
      <template #actions>
        <n-button type="primary" :disabled="!userStore.isLoggedIn" @click="writeShare">
          {{ t('codes.share') }}
        </n-button>
        <RefreshButton :loading="listLoading" :aria-label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <n-spin
      v-show="list.length > 0 || listLoading"
      :show="listLoading"
      class="table-fill"
      content-style="height: 100%; overflow: auto"
    >
      <div v-show="list.length" class="code-grid">
        <article
          v-for="row in list"
          :key="row.id"
          class="code-card"
          role="link"
          tabindex="0"
          @click="openShare(row)"
          @keydown.enter="openShare(row)"
        >
          <div class="code-card__header">
            <BaseAvatar
              :src="row.author.avatar_url ?? undefined"
              :name="row.author.nickname"
              :size="28"
            />
            <span class="code-card__author">{{ row.author.nickname }}</span>
            <span class="code-card__spacer" />
            <n-tag size="small" type="info" bordered>{{ languageLabel(row.language) }}</n-tag>
          </div>
          <h3 class="code-card__title">{{ row.title }}</h3>
          <p class="code-card__excerpt">
            {{ row.description_excerpt || t('codes.noExcerpt') }}
          </p>
          <div class="code-card__footer">
            <span v-if="query.mine && row.status !== 'published'" class="code-card__status">
              {{ t('codes.statusRemoved') }}
            </span>
            <span class="code-card__spacer" />
            <span class="code-card__time">{{ formatDateTime(row.created_at) }}</span>
          </div>
        </article>
      </div>
    </n-spin>
    <div v-show="!listLoading && !list.length" class="table-fill-empty share-empty">
      {{ query.mine ? t('codes.mineEmpty') : t('codes.empty') }}
    </div>

    <div class="share-pagination">
      <n-pagination
        :page="paging.page.value"
        :page-size="paging.pageSize.value"
        :item-count="paging.total.value"
        :disabled="listLoading"
        @update:page="
          (p: number) => {
            paging.changePage(p)
            load()
          }
        "
      />
    </div>
  </WorkbenchShell>
</template>

<style scoped>
/* 高度链与题解页同款：page-fill 无定高，全链 flex 伸缩 */
.code-grid {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
  gap: 14px;
}
.code-card {
  padding: 14px 16px;
  background: var(--app-card-bg);
  border: 1px solid var(--app-border);
  border-radius: 3px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  transition:
    border-color 0.15s,
    box-shadow 0.15s,
    transform 0.15s;
}
.code-card:hover {
  border-color: var(--app-primary);
  box-shadow: 0 4px 16px rgb(15 23 42 / 10%);
}
.code-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.code-card__author {
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.code-card__spacer {
  flex: 1;
}
.code-card__title {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 2.9em;
  transition: color 0.15s;
}
.code-card:hover .code-card__title {
  color: var(--app-primary);
}
.code-card__excerpt {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--app-text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 2em;
}
.code-card__footer {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--app-border);
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.code-card__status {
  color: #f0a020;
}
.share-empty {
  min-height: 240px;
}
.share-pagination {
  margin-top: auto;
  display: flex;
  justify-content: flex-end;
  padding: 10px 4px 2px;
}
</style>
