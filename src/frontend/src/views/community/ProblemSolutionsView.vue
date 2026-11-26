<script setup lang="ts">
/**
 * 题解页（docs/contracts/community.md）：官方题解 + 题解分享双 tab。
 * 各业务上下文（题库 / 题单 / 比赛 / 组织）复用本组件，返回与跳转封闭在当前上下文；
 * 比赛进行中门禁由后端 3002 拦截（错误信封提示）。
 */
import { computed, onActivated, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ChatDotRound as ChatDotRoundIcon } from '@element-plus/icons-vue'

import { deleteSolution, getEditorial, getSolution, listSolutions } from '@/api/community'
import BaseAvatar from '@/components/BaseAvatar.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import CommentSection from '@/components/community/CommentSection.vue'
import ReportDialog from '@/components/community/ReportDialog.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { usePagination } from '@/composables/usePagination'
import { useUserStore } from '@/stores/user'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { EditorialView, SolutionDetail, SolutionSummary } from '@/types'

type SolutionTagType = 'success' | 'warning' | 'error'

const STATUS_TAG: Record<string, { type: SolutionTagType; key: string }> = {
  published: { type: 'success', key: 'published' },
  removed: { type: 'error', key: 'removed' },
}

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

/** 题目 id：题库路由取 params.id；题单 / 比赛 / 组织上下文路由取 params.problemId */
const problemId = computed(() => String(route.params.problemId ?? route.params.id))
/** 上下文题目详情路径（返回写题页；本页路由仅接入题库 / 题单 / 比赛 / 组织上下文） */
const problemPath = computed(() => {
  if (route.params.orgId) {
    return `/me/orgs/${String(route.params.orgId)}/problems/${problemId.value}`
  }
  if (route.params.setId) {
    return `/problem-sets/${String(route.params.setId)}/problems/${problemId.value}`
  }
  if (route.params.cid) {
    return `/contests/${String(route.params.cid)}/problems/${problemId.value}`
  }
  return `/problems/${problemId.value}`
})
const solutionsBase = computed(() => `${problemPath.value}/solutions`)

/** tab 为纯本地状态：不写入 URL query —— query 变化会改变 fullPath，
 * 触发 AppLayout 按 fullPath 换入 keepAlive 缓存实例，复活实例的过期
 * activeTab 与 URL 脱节，表现为切换需点击两次 */
const activeTab = ref<'official' | 'share'>('official')

// ---- 官方题解 ----
const officialLoading = ref(false)
const editorial = ref<EditorialView | null>(null)

async function loadEditorial() {
  officialLoading.value = true
  try {
    editorial.value = await getEditorial(problemId.value)
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    officialLoading.value = false
  }
}

// ---- 题解分享 ----
const list = ref<SolutionSummary[]>([])
const listLoading = ref(false)
const mine = ref(false)
const paging = usePagination({ defaultPageSize: 10 })

async function loadList() {
  const seq = paging.beginLoad()
  listLoading.value = true
  try {
    const res = await listSolutions(problemId.value, {
      page: paging.page.value,
      page_size: paging.pageSize.value,
      mine: mine.value || undefined,
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
  loadList()
}

function onMineChange(value: boolean) {
  mine.value = value
  onSearch()
}

// ---- 卡片原地展开（列表接口仅含摘要，展开时懒加载全文；详情页保留作深链入口） ----
const expandedIds = ref<Set<string>>(new Set())
const detailCache = reactive(new Map<string, SolutionDetail>())
const loadingDetail = ref(new Set<string>())
const reportVisible = ref(false)
const reportTargetId = ref('')

function isExpanded(id: string) {
  return expandedIds.value.has(id)
}

async function ensureDetail(id: string) {
  if (detailCache.has(id) || loadingDetail.value.has(id)) return
  loadingDetail.value = new Set(loadingDetail.value).add(id)
  try {
    detailCache.set(id, await getSolution(id))
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
    const next = new Set(expandedIds.value)
    next.delete(id)
    expandedIds.value = next
  } finally {
    const nextLoading = new Set(loadingDetail.value)
    nextLoading.delete(id)
    loadingDetail.value = nextLoading
  }
}

async function toggleCard(row: SolutionSummary) {
  const next = new Set(expandedIds.value)
  if (next.has(row.id)) {
    next.delete(row.id)
    expandedIds.value = next
    return
  }
  next.add(row.id)
  expandedIds.value = next
  await ensureDetail(row.id)
}

/** keepAlive 激活时重建展开卡片的正文缓存（编辑页保存返回后内容可能已变更） */
onActivated(() => {
  detailCache.clear()
  for (const id of expandedIds.value) void ensureDetail(id)
})

function editSolution(row: SolutionSummary) {
  void router.push(`${solutionsBase.value}/${row.id}/edit`)
}

function removeSolution(row: SolutionSummary) {
  confirmAsyncDialog({
    title: t('problems.solutions.deleteTitle'),
    content: t('problems.solutions.deleteConfirm'),
    positiveText: t('action.confirm'),
    action: () => deleteSolution(row.id),
    successMessage: t('common.success'),
    onAfterSuccess: () => {
      detailCache.delete(row.id)
      const next = new Set(expandedIds.value)
      next.delete(row.id)
      expandedIds.value = next
      loadList()
    },
  })
}

function openReport(row: SolutionSummary) {
  reportTargetId.value = row.id
  reportVisible.value = true
}

function isOwner(row: SolutionSummary) {
  return row.author.id === userStore.user?.id
}

function writeSolution() {
  void router.push(`${solutionsBase.value}/new`)
}

function goBack() {
  void router.push(problemPath.value)
}

function statusTag(status: string) {
  return STATUS_TAG[status] ?? { type: 'info' as SolutionTagType, key: status }
}

watch(
  activeTab,
  (tab) => {
    if (tab === 'share' && !list.value.length && !listLoading.value) loadList()
  },
  { immediate: false },
)

onMounted(() => {
  void loadEditorial()
  void loadList()
})
</script>

<template>
  <WorkbenchShell>
    <template #header-extra>
      <n-button secondary @click="goBack">
        {{ t('problems.solutions.backToProblem') }}
      </n-button>
    </template>

    <!-- 不用 animated：动画模式下 naive 会在 pane-wrapper 内联内容高度，打断 height:100% 链，
         内容区无法 flex 拉伸（分页贴不上底） -->
    <n-tabs v-model:value="activeTab" type="line" class="solutions-tabs">
      <!-- 官方题解 -->
      <n-tab-pane
        name="official"
        :tab="t('problems.solutions.officialTab')"
        display-directive="show"
      >
        <!-- 空态为 n-spin 的兄弟节点（frontend.md 空态规范：v-show 互斥，不嵌进 spin 内部）；
             两个 flex:1 兄弟同时挂载会对半分空间，内容区在「加载中或有数据」时才挂 -->
        <n-spin
          v-show="officialLoading || editorial?.solution"
          :show="officialLoading"
          class="table-fill"
          content-style="height: 100%; overflow: auto"
        >
          <div class="official-content">
            <MarkdownView :source="editorial?.solution" />
          </div>
        </n-spin>
        <div
          v-show="!officialLoading && !editorial?.solution"
          class="table-fill-empty official-empty"
        >
          <div class="official-empty__inner">
            <p>{{ t('problems.solutions.officialEmpty') }}</p>
            <p v-if="editorial?.can_manage" class="official-empty__hint">
              {{ t('problems.solutions.officialManageHint') }}
            </p>
          </div>
        </div>
      </n-tab-pane>

      <!-- 题解分享 -->
      <n-tab-pane name="share" :tab="t('problems.solutions.shareTab')" display-directive="show">
        <div class="share-pane">
          <SearchFilterBar :show-search="false">
            <n-checkbox
              :checked="mine"
              @update:checked="
                (v: boolean) => {
                  onMineChange(v)
                }
              "
            >
              {{ t('problems.solutions.mineOnly') }}
            </n-checkbox>
            <template #actions>
              <n-button type="primary" :disabled="!userStore.isLoggedIn" @click="writeSolution">
                {{ t('problems.solutions.write') }}
              </n-button>
              <RefreshButton
                :loading="listLoading"
                :aria-label="t('action.refresh')"
                @click="loadList"
              />
            </template>
          </SearchFilterBar>

          <n-spin
            v-show="list.length > 0 || listLoading"
            :show="listLoading"
            class="table-fill"
            content-style="height: 100%; overflow: auto"
          >
            <div v-show="list.length" class="solution-list">
              <article
                v-for="row in list"
                :key="row.id"
                class="solution-card"
                role="button"
                tabindex="0"
                :aria-expanded="isExpanded(row.id)"
                @click="toggleCard(row)"
                @keydown.enter="toggleCard(row)"
              >
                <div class="solution-card__header">
                  <BaseAvatar
                    :src="row.author.avatar_url ?? undefined"
                    :name="row.author.nickname"
                    :size="38"
                  />
                  <div class="solution-card__byline">
                    <span class="solution-card__author">{{ row.author.nickname }}</span>
                    <span class="solution-card__time">{{ formatDateTime(row.updated_at) }}</span>
                  </div>
                  <n-tag
                    v-if="mine && row.status !== 'published'"
                    size="small"
                    :type="statusTag(row.status).type"
                    bordered
                  >
                    {{ t(`problems.solutions.status.${statusTag(row.status).key}`) }}
                  </n-tag>
                </div>

                <h3 class="solution-card__title">{{ row.title }}</h3>
                <p v-if="!isExpanded(row.id)" class="solution-card__excerpt">
                  {{ row.excerpt || t('problems.solutions.noExcerpt') }}
                </p>

                <!-- 展开区：全文 + 本人操作 / 举报 + 评论区（点击不冒泡，避免误触折叠） -->
                <div v-if="isExpanded(row.id)" class="solution-card__body" @click.stop>
                  <div v-if="userStore.isLoggedIn" class="solution-card__actions">
                    <n-button v-if="isOwner(row)" text size="small" @click="editSolution(row)">
                      {{ t('action.edit') }}
                    </n-button>
                    <n-button
                      v-if="isOwner(row)"
                      text
                      size="small"
                      type="error"
                      @click="removeSolution(row)"
                    >
                      {{ t('action.delete') }}
                    </n-button>
                    <n-button v-else text size="small" @click="openReport(row)">
                      {{ t('community.report.short') }}
                    </n-button>
                  </div>
                  <div v-if="detailCache.get(row.id)" class="solution-card__content">
                    <MarkdownView :source="detailCache.get(row.id)!.content" />
                  </div>
                  <div v-else class="solution-card__loading">
                    <n-spin size="small" />
                  </div>
                  <CommentSection target-type="solution" :target-id="row.id" />
                </div>

                <footer class="solution-card__footer">
                  <span class="solution-card__stat">
                    <n-icon :size="14"><ChatDotRoundIcon /></n-icon>
                    {{ t('problems.solutions.commentCount', { count: row.comment_count }) }}
                  </span>
                  <span class="solution-card__spacer" />
                  <button type="button" class="solution-card__toggle" @click.stop="toggleCard(row)">
                    {{
                      isExpanded(row.id)
                        ? t('problems.solutions.collapse')
                        : t('problems.solutions.expand')
                    }}
                    <svg
                      class="solution-card__chevron"
                      :class="{ 'solution-card__chevron--open': isExpanded(row.id) }"
                      viewBox="0 0 16 16"
                      width="12"
                      height="12"
                      aria-hidden="true"
                    >
                      <path
                        d="M3 6l5 5 5-5"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.6"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                    </svg>
                  </button>
                </footer>
              </article>
            </div>
          </n-spin>
          <div v-show="!listLoading && !list.length" class="table-fill-empty solution-empty">
            {{ mine ? t('problems.solutions.mineEmpty') : t('problems.solutions.empty') }}
          </div>

          <!-- 分页常驻：空态下也显示（禁用态），带页容量切换 -->
          <div class="share-pagination">
            <n-pagination
              :page="paging.page.value"
              :page-size="paging.pageSize.value"
              :item-count="paging.total.value"
              :disabled="listLoading"
              @update:page="
                (p: number) => {
                  paging.changePage(p)
                  loadList()
                }
              "
            />
          </div>
        </div>
      </n-tab-pane>
    </n-tabs>

    <ReportDialog v-model:show="reportVisible" target-type="solution" :target-id="reportTargetId" />
  </WorkbenchShell>
</template>

<style scoped>
/* 高度链全用 flex 伸缩：.page-fill 只有 min-height（无定高），子元素 height:100% 会退化为内容高度；
   非 animated 模式下 n-tab-pane 就是 .n-tabs 的直接 flex 子元素（无 pane-wrapper 层） */
.solutions-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.solutions-tabs :deep(.n-tabs-nav) {
  flex-shrink: 0;
}
.solutions-tabs :deep(.n-tab-pane) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.official-content {
  max-width: 860px;
  margin: 0 auto;
  width: 100%;
  padding-bottom: 24px;
  overflow: auto;
}
.official-empty__inner {
  text-align: center;
  color: var(--app-text-secondary);
}
.official-empty__hint {
  font-size: 12px;
  margin-top: 6px;
}
.share-pane {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.solution-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
/* 内容卡片：作者行 → 标题（视觉主角）→ 摘要 → 分隔线页脚（评论数 + 展开开关） */
.solution-card {
  padding: 16px 20px 12px;
  background: var(--app-card-bg);
  border: 1px solid var(--app-border);
  border-radius: 3px;
  cursor: pointer;
}
.solution-card__header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.solution-card__byline {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.solution-card__author {
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text);
  line-height: 1.2;
}
.solution-card__time {
  font-size: 12px;
  color: var(--app-text-secondary);
  line-height: 1.2;
}
.solution-card__header .n-tag {
  margin-left: 4px;
}
.solution-card__title {
  margin: 14px 0 0;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.5;
}
.solution-card__excerpt {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.75;
  color: var(--app-text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.solution-card__footer {
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px solid var(--app-border);
  display: flex;
  align-items: center;
  gap: 10px;
}
.solution-card__stat {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12.5px;
  color: var(--app-text-secondary);
}
.solution-card__spacer {
  flex: 1;
}
.solution-card__toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: none;
  background: none;
  padding: 0;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: var(--app-primary);
}
.solution-card__toggle:hover {
  opacity: 0.8;
}
.solution-card__chevron {
  flex-shrink: 0;
}
.solution-card__chevron--open {
  transform: rotate(180deg);
}
.solution-card__body {
  margin-top: 12px;
  cursor: default;
}
.solution-card__actions {
  display: flex;
  justify-content: flex-end;
  gap: 14px;
  margin-bottom: 10px;
}
/* 正文阅读区：浅灰圆角容器与卡片底色区分，限宽保证可读行长 */
.solution-card__content {
  max-width: 860px;
  padding: 14px 18px;
  background: var(--app-muted-bg);
  border-radius: 3px;
}
.solution-card__loading {
  display: grid;
  place-items: center;
  padding: 24px 0;
}
.solution-empty {
  min-height: 240px;
}
/* margin-top:auto 双保险：内容区即使被 naive 内联高度顶开，分页也贴在 share-pane 底部 */
.share-pagination {
  margin-top: auto;
  display: flex;
  justify-content: flex-end;
  padding: 10px 4px 2px;
}
</style>
