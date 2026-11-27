<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, MessageSquare, PenLine } from '@lucide/vue'

import { getEditorial, listSolutions } from '@/api/community'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import FilterCheckbox from '@/components/common/FilterCheckbox.vue'
import MarkdownView from '@/components/common/MarkdownView.vue'
import Pager from '@/components/common/Pager.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemMedia,
  ItemSeparator,
  ItemTitle,
} from '@/components/ui/item'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { usePagination } from '@/composables/usePagination'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'
import { formatDate } from '@/utils/format'
import type { EditorialView, SolutionSummary } from '@/types'
import { useSolutionContext } from './useSolutionContext'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()
const { problemId, problemBase, solutionsBase } = useSolutionContext()
const activeTab = ref<'official' | 'share'>('official')

const editorial = ref<EditorialView | null>(null)
const editorialLoading = ref(false)

const solutions = ref<SolutionSummary[]>([])
const loading = ref(false)
const keyword = ref('')
const mineOnly = ref(false)
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

async function loadEditorial(): Promise<void> {
  editorialLoading.value = true
  try {
    editorial.value = await getEditorial(problemId.value)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    editorialLoading.value = false
  }
}

async function loadSolutions(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listSolutions(problemId.value, {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      mine: mineOnly.value || undefined,
    })
    if (!isCurrent(seq)) return
    solutions.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

function onSearch(): void {
  resetPage()
  void loadSolutions()
}

function onMineChange(value: boolean): void {
  mineOnly.value = value
  onSearch()
}

function onPageChange(value: number): void {
  changePage(value)
  void loadSolutions()
}

function openSolution(solution: SolutionSummary): void {
  void router.push(`${solutionsBase.value}/${solution.id}`)
}

function write(): void {
  void router.push(`${solutionsBase.value}/new`)
}

onMounted(() => {
  void loadEditorial()
  void loadSolutions()
})
</script>

<template>
  <WorkbenchShell :title="t('problems.solutions.title')">
    <template #actions>
      <Button variant="outline" size="sm" @click="router.push(problemBase)">
        <ArrowLeft class="size-4" />
        {{ t('problems.solutions.backToProblem') }}
      </Button>
      <RefreshButton
        :loading="loading || editorialLoading"
        :label="t('action.refresh')"
        @click="
          () => {
            loadEditorial()
            loadSolutions()
          }
        "
      />
    </template>

    <Tabs v-model="activeTab" class="min-h-0 flex-1 gap-2">
      <TabsList class="shrink-0">
        <TabsTrigger value="official" class="px-3 text-[12.5px]">
          {{ t('problems.solutions.officialTab') }}
        </TabsTrigger>
        <TabsTrigger value="share" class="px-3 text-[12.5px]">
          {{ t('problems.solutions.shareTab') }}
        </TabsTrigger>
      </TabsList>

      <TabsContent value="official" class="min-h-0 overflow-y-auto">
        <div v-if="editorialLoading" class="grid h-40 place-items-center">
          <span class="text-[13px] text-muted-foreground">{{ t('common.loading') }}</span>
        </div>
        <Card v-else class="px-5 py-4">
          <MarkdownView v-if="editorial?.solution" :source="editorial.solution" />
          <p v-else class="py-8 text-center text-[13px] text-muted-foreground">
            {{ t('problems.solutions.officialEmpty') }}
          </p>
          <p
            v-if="editorial?.can_manage"
            class="mt-4 border-t border-border pt-3 text-[12px] text-muted-foreground"
          >
            {{ t('problems.solutions.officialManageHint') }}
          </p>
        </Card>
      </TabsContent>

      <TabsContent value="share" class="flex min-h-0 flex-col gap-3">
        <SearchFilterBar
          :keyword="keyword"
          :placeholder="t('problems.solutions.searchPlaceholder')"
          @update:keyword="keyword = $event"
          @search="onSearch"
          @reset="onSearch"
        >
          <template #actions>
            <FilterCheckbox
              v-if="userStore.isLoggedIn"
              id="solutions-mine"
              :model-value="mineOnly"
              :label="t('problems.solutions.mineOnly')"
              @update:model-value="onMineChange"
            />
            <Button v-if="userStore.isLoggedIn" size="toolbar" @click="write">
              <PenLine class="size-4" />
              {{ t('problems.solutions.write') }}
            </Button>
          </template>
        </SearchFilterBar>

        <Card class="flex min-h-0 flex-1 flex-col overflow-hidden p-0">
          <div v-if="loading" class="flex flex-col gap-4 p-4">
            <div v-for="index in 5" :key="index" class="flex items-start gap-3">
              <Skeleton class="size-10 shrink-0 rounded-full" />
              <div class="min-w-0 flex-1 space-y-2">
                <Skeleton class="h-4 w-1/2" />
                <Skeleton class="h-3 w-full" />
                <Skeleton class="h-3 w-2/5" />
              </div>
            </div>
          </div>

          <div v-else-if="!solutions.length" class="grid min-h-0 flex-1 place-items-center p-6">
            <EmptyState
              :text="t(mineOnly ? 'problems.solutions.mineEmpty' : 'problems.solutions.empty')"
            />
          </div>

          <div v-else class="min-h-0 flex-1 overflow-y-auto">
            <ItemGroup>
              <template v-for="(solution, index) in solutions" :key="solution.id">
                <Item
                  class="cursor-pointer flex-nowrap gap-3 rounded-none px-4 py-3.5 hover:bg-muted/40"
                  @click="openSolution(solution)"
                >
                  <ItemMedia>
                    <BaseAvatar
                      kind="user"
                      :src="solution.author.avatar_url"
                      :name="solution.author.nickname"
                      :size="40"
                    />
                  </ItemMedia>
                  <ItemContent class="min-w-0 gap-1">
                    <div class="flex min-w-0 items-center gap-2">
                      <ItemTitle
                        class="w-auto min-w-0 flex-1 truncate text-[14px] font-semibold"
                        :title="solution.title"
                      >
                        {{ solution.title }}
                      </ItemTitle>
                      <ToneBadge
                        v-if="solution.status === 'removed'"
                        tone="default"
                        :label="t('problems.solutions.status.removed')"
                        class="shrink-0"
                      />
                    </div>
                    <ItemDescription class="line-clamp-1 text-[12.5px]">
                      {{ solution.excerpt || t('problems.solutions.noExcerpt') }}
                    </ItemDescription>
                    <div
                      class="flex items-center gap-1.5 text-[11.5px] text-muted-foreground"
                    >
                      <span class="min-w-0 truncate">{{ solution.author.nickname }}</span>
                      <span aria-hidden="true">·</span>
                      <span class="shrink-0 tabular-nums">
                        {{ formatDate(solution.updated_at) }}
                      </span>
                    </div>
                  </ItemContent>
                  <ItemActions class="shrink-0">
                    <span
                      class="flex items-center gap-1 text-[12px] tabular-nums text-muted-foreground"
                    >
                      <MessageSquare class="size-3.5" />
                      {{ solution.comment_count }}
                    </span>
                  </ItemActions>
                </Item>
                <ItemSeparator v-if="index < solutions.length - 1" />
              </template>
            </ItemGroup>
          </div>
        </Card>

        <div class="shrink-0 px-1">
          <Pager
            :page="page"
            :page-size="pageSize"
            :total="total"
            @update:page="onPageChange"
          >
            <template #left>
              <span class="tabular-nums">{{ t('app.totalItems', { count: total }) }}</span>
            </template>
          </Pager>
        </div>
      </TabsContent>
    </Tabs>
  </WorkbenchShell>
</template>