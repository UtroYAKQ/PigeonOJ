<script setup lang="ts">
/**
 * 代码分享管理（docs/contracts/community.md「代码广场」）：全状态列表 + 预览弹窗
 * （说明 / 只读代码 / 评论治理下钻）。举报处理页经 ?code=<id> 跳转本页预览。
 */
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { NButton, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import { adminGetCodeShare, adminListCodeShares, adminSetCodeShareStatus } from '@/api/community'
import { getCodeShare } from '@/api/community'
import BaseAvatar from '@/components/BaseAvatar.vue'
import CodeEditor from '@/components/CodeEditor.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { usePagination } from '@/composables/usePagination'
import { languageOptions } from '@/constants/languages'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { AdminCodeShare, CodeShareStatus } from '@/types'

const { t } = useI18n()
const route = useRoute()

const loading = ref(false)
const list = ref<AdminCodeShare[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()
const query = reactive({
  keyword: '',
  status: null as CodeShareStatus | null,
  language: null as string | null,
})

const previewVisible = ref(false)
const previewRow = ref<AdminCodeShare | null>(null)
const previewDetail = ref<{ description: string | null; code: string } | null>(null)
const previewLoading = ref(false)

const statusOptions = computed(() => [
  { label: t('codes.statusPublished'), value: 'published' as CodeShareStatus },
  { label: t('codes.statusRemoved'), value: 'removed' as CodeShareStatus },
])

const languageFilterOptions = computed(() => [
  { label: t('codes.allLanguages'), value: '' },
  ...languageOptions.map((o) => ({ label: o.label, value: o.value })),
])

const STATUS_TAG: Record<CodeShareStatus, 'success' | 'error'> = {
  published: 'success',
  removed: 'error',
}

function languageLabel(value: string) {
  return languageOptions.find((o) => o.value === value)?.label ?? value
}

async function load() {
  const seq = beginLoad()
  loading.value = true
  try {
    const res = await adminListCodeShares({
      page: page.value,
      page_size: pageSize.value,
      status: query.status ?? undefined,
      keyword: query.keyword || undefined,
      language: (query.language || undefined) as undefined,
    })
    if (!isCurrent(seq)) return
    list.value = res.items
    total.value = res.total
  } catch (e) {
    if (!isCurrent(seq)) return
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}
onMounted(() => {
  load()
  // 举报处理页联动：?code=<id> 打开预览
  const codeParam = route.query.code
  if (typeof codeParam === 'string' && codeParam) {
    void openPreviewById(codeParam)
  }
})
function onSearch() {
  resetPage()
  load()
}

async function openPreviewById(id: string) {
  try {
    const row = await adminGetCodeShare(id)
    await openPreview(row)
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('admin.codes.previewNotFound'))
  }
}

async function openPreview(row: AdminCodeShare) {
  previewRow.value = row
  previewDetail.value = null
  previewVisible.value = true
  previewLoading.value = true
  try {
    previewDetail.value = await getCodeShare(row.id)
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
    previewVisible.value = false
  } finally {
    previewLoading.value = false
  }
}

function toggleStatus(row: AdminCodeShare) {
  const removing = row.status !== 'removed'
  const run = () =>
    adminSetCodeShareStatus(row.id, removing ? 'removed' : 'published').then(() => {
      row.status = removing ? 'removed' : 'published'
      if (previewRow.value?.id === row.id) previewRow.value = { ...row }
    })
  if (removing) {
    confirmAsyncDialog({
      title: t('admin.codes.removeTitle'),
      content: t('admin.codes.removeConfirm', { title: row.title }),
      positiveText: t('action.confirm'),
      action: run,
      successMessage: t('common.success'),
    })
  } else {
    void run().then(() => message.success(t('common.success')))
  }
}

const columns = computed<DataTableColumns<AdminCodeShare>>(() => [
  {
    title: t('admin.codes.title'),
    key: 'title',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (row) => h('a', { class: 'cell-link', onClick: () => openPreview(row) }, row.title),
  },
  {
    title: t('admin.codes.language'),
    key: 'language',
    width: 110,
    render: (row) => languageLabel(row.language),
  },
  {
    title: t('admin.codes.author'),
    key: 'author',
    width: 140,
    render(row) {
      return h('div', { class: 'cell-author' }, [
        h(BaseAvatar, {
          src: row.author.avatar_url ?? undefined,
          name: row.author.nickname,
          size: 24,
        }),
        h('span', row.author.nickname),
      ])
    },
  },
  {
    title: t('admin.codes.status'),
    key: 'status',
    width: 90,
    render: (row) =>
      h(
        NTag,
        { size: 'small', type: STATUS_TAG[row.status], bordered: false },
        { default: () => t(`codes.status${row.status === 'published' ? 'Published' : 'Removed'}`) },
      ),
  },
  {
    title: t('admin.codes.updatedAt'),
    key: 'updated_at',
    width: 160,
    render: (row) => formatDateTime(row.updated_at),
  },
  {
    title: t('admin.codes.actions'),
    key: 'actions',
    width: 150,
    fixed: 'right',
    render(row) {
      return h('div', { class: 'cell-actions' }, [
        h(
          NButton,
          { text: true, type: 'primary', onClick: () => openPreview(row) },
          { default: () => t('admin.codes.preview') },
        ),
        h(
          NButton,
          {
            text: true,
            type: row.status === 'removed' ? 'success' : 'warning',
            onClick: () => toggleStatus(row),
          },
          {
            default: () =>
              row.status === 'removed' ? t('admin.solutions.restore') : t('admin.solutions.remove'),
          },
        ),
      ])
    },
  },
])
</script>

<template>
  <WorkbenchShell>
    <SearchFilterBar
      :keyword="query.keyword"
      :placeholder="t('admin.codes.search')"
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
        style="width: 140px"
        :options="languageFilterOptions"
        :placeholder="t('codes.allLanguages')"
        @update:value="onSearch"
      />
      <n-select
        v-model:value="query.status"
        clearable
        style="width: 140px"
        :options="statusOptions"
        :placeholder="t('common.allStatus')"
        @update:value="onSearch"
      />
      <template #actions>
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="onSearch" />
      </template>
    </SearchFilterBar>

    <PaginatedDataTable
      show-size-picker
      :columns="columns"
      :data="list"
      :loading="loading"
      :total="total"
      v-model:page="page"
      v-model:page-size="pageSize"
      :page-sizes="[10, 20, 50]"
      :empty-text="t('admin.codes.empty')"
      :table-props="{ scrollX: 1000 }"
      @update:page="
        (p: number) => {
          changePage(p)
          load()
        }
      "
      @update:page-size="
        (s: number) => {
          changeSize(s)
          load()
        }
      "
    />

    <!-- 分享预览：说明 + 只读代码 + 评论治理（admin 模式含被删评论与恢复） -->
    <n-modal
      v-model:show="previewVisible"
      preset="card"
      style="width: min(880px, 94vw)"
      :title="previewRow?.title"
    >
      <n-spin :show="previewLoading">
        <div v-if="previewRow" class="preview">
          <div class="preview__meta">
            <BaseAvatar
              :src="previewRow.author.avatar_url ?? undefined"
              :name="previewRow.author.nickname"
              :size="26"
            />
            <span class="preview__author">{{ previewRow.author.nickname }}</span>
            <span>{{ formatDateTime(previewRow.created_at) }}</span>
            <n-tag size="small" type="info" bordered>{{
              languageLabel(previewRow.language)
            }}</n-tag>
            <n-tag size="small" :type="STATUS_TAG[previewRow.status]" bordered>
              {{ t(`codes.status${previewRow.status === 'published' ? 'Published' : 'Removed'}`) }}
            </n-tag>
            <span class="preview__spacer" />
            <n-button
              size="tiny"
              :type="previewRow.status === 'removed' ? 'success' : 'warning'"
              secondary
              @click="toggleStatus(previewRow)"
            >
              {{
                previewRow.status === 'removed'
                  ? t('admin.solutions.restore')
                  : t('admin.solutions.remove')
              }}
            </n-button>
          </div>
          <p v-if="previewDetail?.description" class="preview__description">
            {{ previewDetail.description }}
          </p>
          <div v-if="previewDetail" class="preview__code">
            <CodeEditor
              :model-value="previewDetail.code"
              :language="previewRow.language"
              read-only
            />
          </div>
        </div>
      </n-spin>
    </n-modal>
  </WorkbenchShell>
</template>

<style scoped>
.cell-link {
  color: var(--app-primary);
  cursor: pointer;
}
.cell-link:hover {
  text-decoration: underline;
}
.cell-author {
  display: flex;
  align-items: center;
  gap: 6px;
}
.preview__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.preview__author {
  font-weight: 600;
  color: var(--app-text);
}
.preview__spacer {
  flex: 1;
}
.preview__description {
  margin: 12px 0;
  padding: 12px 16px;
  background: var(--app-muted-bg);
  border-radius: 3px;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
.preview__code {
  margin-bottom: 6px;
}
.preview__code :deep(.code-editor) {
  height: 320px;
}
</style>
