<script setup lang="ts">
import { CirclePlus, EditPen, Tickets, TurnOff } from '@element-plus/icons-vue'
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NButton, NIcon, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import { archiveProblem, exportProblemXml, exportProblemsZip, importFpsProblems, listProblems } from '@/api/problems'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import RefreshButton from '@/components/RefreshButton.vue'
import { problemStatusTagType, problemStatusLabelKey } from '@/constants/problemStatus'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import type { FpsImportResult, PageResult, ProblemSummary } from '@/types'

type ProblemStatus = 'draft' | 'published' | 'archived'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const list = ref<ProblemSummary[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage } = usePagination()
const query = reactive({
  keyword: '',
  status: '' as ProblemStatus | '',
  ownership: '' as '' | 'solo' | 'team',
})

/** FPS 题库导入 / 导出（docs/contracts/problems.md「FPS 题库导入 / 导出」）：
 * 同一弹窗双 tab；导入上传 ZIP，导出按列表勾选（跨页保留选中） */
const importVisible = ref(false)
const importing = ref(false)
const importFile = ref<File | null>(null)
const importResult = ref<FpsImportResult | null>(null)
const IMPORT_MAX_BYTES = 64 * 1024 * 1024
const importInput = ref<HTMLInputElement>()
const modalTab = ref<'import' | 'export'>('import')
const exporting = ref(false)
/** 勾选的题目 id（批量导出；跨页/翻页保留） */
const checkedKeys = ref<string[]>([])

function chooseImportFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  ;(event.target as HTMLInputElement).value = ''
  if (!file) return
  if (!/\.(zip|xml|fps)$/i.test(file.name)) {
    message.error(t('problems.importFps.invalidType'))
    return
  }
  if (file.size > IMPORT_MAX_BYTES) {
    message.error(t('problems.importFps.tooLarge'))
    return
  }
  importFile.value = file
  importResult.value = null
}

function importStatusType(status: string): 'success' | 'warning' | 'error' | 'default' {
  if (status === 'published') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'draft' || status === 'draft_spj') return 'warning'
  return 'default'
}

function importStatusLabel(status: string): string {
  return t(`problems.importFps.status_${status}`)
}

async function doImport() {
  if (!importFile.value || importing.value) return
  importing.value = true
  try {
    importResult.value = await importFpsProblems(importFile.value)
    if (importResult.value.imported > 0) await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.importFps.failed'))
  } finally {
    importing.value = false
  }
}

function openImport() {
  importFile.value = null
  importResult.value = null
  modalTab.value = 'import'
  importVisible.value = true
}

/** 批量导出 ZIP（勾选 N 题）；单题 fps.xml 仅在恰好勾选 1 题时可用 */
async function doExport(kind: 'zip' | 'xml') {
  if (exporting.value || !checkedKeys.value.length) return
  if (kind === 'xml' && checkedKeys.value.length !== 1) return
  exporting.value = true
  try {
    if (kind === 'zip') {
      await exportProblemsZip(checkedKeys.value)
    } else {
      await exportProblemXml(checkedKeys.value[0])
    }
    message.success(t('problems.importFps.exportSuccess'))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.importFps.failed'))
  } finally {
    exporting.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const result: PageResult<ProblemSummary> = await listProblems({
      page: page.value,
      page_size: pageSize.value,
      keyword: query.keyword || undefined,
      scope: 'mine',
      status: query.status || undefined,
      ownership: query.ownership || undefined,
    })
    list.value = result.items
    total.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.list.loadFailed'))
  } finally {
    loading.value = false
  }
}

function switchStatus(value: string) {
  query.status = value as ProblemStatus | ''
  resetPage()
  load()
}
function switchOwnership(value: string | null) {
  query.ownership = (value ?? '') as '' | 'solo' | 'team'
  resetPage()
  load()
}

/** 来源筛选项：全站题 / 团队题（引用快照 + 团队直建） */
const ownershipOptions = computed(() => [
  { label: t('problems.mine.ownershipSolo'), value: 'solo' },
  { label: t('problems.mine.ownershipTeam'), value: 'team' },
])
function onSearch() {
  resetPage()
  load()
}
function goEdit(row: ProblemSummary) {
  router.push(`/admin/problems/${row.id}/edit/statement`)
}
function goDetail(row: ProblemSummary) {
  // 管理动线只读预览：留在后台，不进前台写题页
  router.push(`/admin/problems/${row.id}/preview`)
}
function goSubmissions(row: ProblemSummary) {
  router.push(`/admin/problems/${row.id}/submissions`)
}

function doArchive(row: ProblemSummary) {
  confirmAsyncDialog({
    title: t('problems.detail.archive'),
    content: t('problems.mine.archiveConfirm'),
    positiveText: t('problems.detail.archive'),
    action: async () => {
      Object.assign(row, await archiveProblem(row.id))
    },
    successMessage: t('problems.detail.archiveSuccess'),
    onAfterSuccess: () => load(),
  })
}

onMounted(load)

const columns = computed<DataTableColumns<ProblemSummary>>(() => [
  {
    // 勾选列：批量导出选题（跨页保留选中，key 为题目 id）
    type: 'selection',
    width: 44,
  },
  {
    title: t('problems.list.name'),
    key: 'title',
    minWidth: 260,
    render(row) {
      return h('div', { class: 'problem-name' }, [
        h('strong', null, row.title),
        h('span', null, `#${(row.id || '').slice(0, 8)}`),
      ])
    },
  },
  {
    title: t('problems.list.type'),
    key: 'status',
    width: 100,
    render(row) {
      return h(
        NTag,
        { size: 'small', bordered: false, type: problemStatusTagType(row.status) },
        { default: () => t(problemStatusLabelKey[row.status] ?? row.status) },
      )
    },
  },
  {
    title: t('problems.list.visibility'),
    key: 'visibility',
    width: 90,
    render(row) {
      // 可见性色彩语义：公开=蓝（info）/ 私有=红（error）；其余可见性随 teams 模块扩展
      return h(
        NTag,
        {
          size: 'small',
          bordered: false,
          type: row.visibility === 'private' ? 'error' : 'info',
        },
        { default: () => t(`problems.visibility.${row.visibility ?? 'public'}`) },
      )
    },
  },
  {
    title: t('problems.list.source'),
    key: 'source',
    width: 80,
    render(row) {
      // 来源：团队题（引用快照 / 团队直建）→「团队题」；其余（全站公开 / 私有）→「全站题」
      const isTeam = row.visibility === 'team_visible' || row.visibility === 'admin_visible'
      return h(
        NTag,
        {
          size: 'small',
          bordered: false,
          type: isTeam ? 'warning' : 'default',
        },
        {
          default: () => t(isTeam ? 'problems.mine.ownershipTeam' : 'problems.mine.ownershipSolo'),
        },
      )
    },
  },
  {
    title: t('problems.manage.shareTitle'),
    key: 'is_verified',
    width: 110,
    render(row) {
      if (row.needs_reverification) {
        return h(
          NTag,
          { size: 'small', bordered: false, type: 'warning' },
          { default: () => t('problems.manage.reverifyTag') },
        )
      }
      return h(
        NTag,
        { size: 'small', bordered: false, type: row.is_verified ? 'success' : 'default' },
        {
          default: () =>
            row.is_verified ? t('problems.manage.verifiedTag') : t('problems.manage.unverifiedTag'),
        },
      )
    },
  },
  {
    title: t('problems.list.limits'),
    key: 'limits',
    width: 180,
    render: (row) => `${row.time_limit_ms} ms / ${row.memory_limit_mb} MB`,
  },
  {
    title: t('action.edit'),
    key: 'actions',
    width: 250,
    fixed: 'right',
    render(row) {
      const buttons: ReturnType<typeof h>[] = []
      // 行内操作：text 按钮 + 语义图标（docs/frontend.md 按钮规范）；归档为唯一危险操作。
      // 点击必须 stopPropagation，否则冒泡到行 onClick 会把路由覆盖成行的目标（如预览页）
      function actionButton(
        icon: typeof Tickets,
        label: string,
        onClick: () => void,
        type?: 'primary' | 'error',
      ) {
        return h(
          NButton,
          {
            text: true,
            type,
            class: 'cell-actions__btn',
            onClick: (event: MouseEvent) => {
              event.stopPropagation()
              onClick()
            },
          },
          {
            icon: () => h(NIcon, { size: 14 }, { default: () => h(icon) }),
            default: () => label,
          },
        )
      }
      // 查看不再单设按钮：点击行即进入只读预览（见 rowProps）
      if (row.status === 'draft') {
        buttons.push(
          actionButton(Tickets, t('problems.mine.viewSubmissions'), () => goSubmissions(row)),
          actionButton(EditPen, t('action.edit'), () => goEdit(row), 'primary'),
        )
      } else if (row.status === 'published') {
        buttons.push(
          actionButton(Tickets, t('problems.mine.viewSubmissions'), () => goSubmissions(row)),
          actionButton(EditPen, t('action.edit'), () => goEdit(row), 'primary'),
          actionButton(TurnOff, t('problems.detail.archive'), () => doArchive(row), 'error'),
        )
      } else {
        buttons.push(
          actionButton(Tickets, t('problems.mine.viewSubmissions'), () => goSubmissions(row)),
        )
      }
      return h('div', { class: 'cell-actions' }, buttons)
    },
  },
])

function rowProps(row: ProblemSummary) {
  // 点击行即查看（只读预览，留在管理后台）：草稿 / 已发布 / 已归档一致；
  // 勾选列的点击不冒泡（否则勾选即跳预览页）
  return {
    style: 'cursor: pointer;',
    onClick: (event: MouseEvent) => {
      if ((event.target as HTMLElement).closest('.n-checkbox')) return
      goDetail(row)
    },
  }
}
</script>

<template>
  <WorkbenchShell>
    <SearchFilterBar
      :keyword="query.keyword"
      :placeholder="t('problems.mine.search')"
      search-width="280px"
      @update:keyword="
        (v: string) => {
          query.keyword = v
        }
      "
      @search="onSearch"
      @reset="onSearch"
    >
      <n-select
        :value="query.ownership || null"
        clearable
        style="width: 160px"
        :options="ownershipOptions"
        :placeholder="t('problems.mine.ownershipAll')"
        @update:value="switchOwnership"
      />
      <template #actions>
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
        <n-button secondary @click="openImport">
          <template #icon>
            <n-icon :component="Tickets" />
          </template>
          {{ t('problems.importFps.button') }}
        </n-button>
        <n-button type="primary" @click="router.push('/admin/problems/new')">
          <template #icon>
            <n-icon :component="CirclePlus" />
          </template>
          {{ t('problems.list.create') }}
        </n-button>
      </template>
    </SearchFilterBar>

    <n-tabs
      type="line"
      size="small"
      class="status-tabs"
      :value="query.status || 'all'"
      @update:value="switchStatus"
    >
      <n-tab-pane name="all" :tab="t('problems.mine.all')" />
      <n-tab-pane name="draft" :tab="t('problems.list.statusDraft')" />
      <n-tab-pane name="published" :tab="t('problems.list.statusPublished')" />
      <n-tab-pane name="archived" :tab="t('problems.list.statusArchived')" />
    </n-tabs>

    <PaginatedDataTable
      show-size-picker
      :columns="columns"
      :data="list"
      :loading="loading"
      :total="total"
      v-model:page="page"
      v-model:page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      :empty-text="t('problems.mine.empty')"
      :table-props="{
        scrollX: 1080,
        rowProps,
        rowKey: (row: ProblemSummary) => row.id,
        checkedRowKeys: checkedKeys,
        onUpdateCheckedRowKeys: (keys: Array<string | number>) => {
          checkedKeys = keys as string[]
        },
      }"
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
    >
      <template #pager-left>
        <span class="pager__total">{{ t('problems.list.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedDataTable>

    <!-- FPS 题库导入 / 导出弹窗：双 tab；导入上传 ZIP，导出按列表勾选 -->
    <n-modal
      v-model:show="importVisible"
      preset="card"
      :title="t('problems.importFps.title')"
      style="width: min(600px, 92vw)"
    >
      <n-tabs v-model:value="modalTab" type="line" size="small" animated>
        <n-tab-pane name="import" :tab="t('problems.importFps.tabImport')">
          <div class="import-fps">
            <p class="import-fps__hint">{{ t('problems.importFps.hint') }}</p>
            <div class="import-fps__picker">
              <input
                ref="importInput"
                type="file"
                accept=".zip,.xml,.fps"
                class="import-fps__input"
                @change="chooseImportFile"
              />
              <n-button size="small" @click="importInput?.click()">
                {{ t('problems.importFps.choose') }}
              </n-button>
              <span v-if="importFile" class="import-fps__file">{{ importFile.name }}</span>
              <n-button
                type="primary"
                size="small"
                class="import-fps__start"
                :disabled="!importFile"
                :loading="importing"
                @click="doImport"
              >
                {{ t('problems.importFps.start') }}
              </n-button>
            </div>
            <template v-if="importResult">
              <n-alert
                :type="importResult.imported > 0 ? 'success' : 'warning'"
                class="import-fps__summary"
              >
                {{ t('problems.importFps.summary', { parsed: importResult.total_parsed, imported: importResult.imported }) }}
                <template v-if="importResult.truncated">
                  <br />{{ t('problems.importFps.truncated') }}
                </template>
              </n-alert>
              <div v-if="importResult.results.length" class="import-fps__results">
                <div
                  v-for="(item, index) in importResult.results"
                  :key="`${item.title}-${index}`"
                  class="import-fps__row"
                >
                  <n-tag size="small" :type="importStatusType(item.status)" :bordered="false">
                    {{ importStatusLabel(item.status) }}
                  </n-tag>
                  <span class="import-fps__title">{{ item.title }}</span>
                  <span v-if="item.message" class="import-fps__msg">{{ item.message }}</span>
                </div>
              </div>
            </template>
          </div>
        </n-tab-pane>
        <n-tab-pane name="export" :tab="t('problems.importFps.tabExport')">
          <div class="import-fps">
            <p class="import-fps__hint">{{ t('problems.importFps.exportHint') }}</p>
            <n-alert
              v-if="!checkedKeys.length"
              type="info"
              :bordered="false"
              class="import-fps__summary"
            >
              {{ t('problems.importFps.exportNone') }}
            </n-alert>
            <template v-else>
              <p class="import-fps__selected">
                {{ t('problems.importFps.selectedCount', { count: checkedKeys.length }) }}
              </p>
              <div class="import-fps__actions">
                <n-button
                  size="small"
                  :disabled="checkedKeys.length !== 1"
                  :loading="exporting"
                  @click="doExport('xml')"
                >
                  {{ t('problems.importFps.exportXml') }}
                </n-button>
                <n-button
                  type="primary"
                  size="small"
                  :loading="exporting"
                  @click="doExport('zip')"
                >
                  {{ t('problems.importFps.exportZip') }}
                </n-button>
              </div>
            </template>
          </div>
        </n-tab-pane>
      </n-tabs>
    </n-modal>
  </WorkbenchShell>
</template>

<style scoped>
.status-tabs {
  margin-bottom: 4px;
}
.problem-name {
  display: grid;
  gap: 4px;
}
.problem-name strong {
  font-size: 14px;
}
.problem-name span {
  color: var(--app-text-secondary);
  font-size: 12px;
}
/* 行内操作按钮增强：中等字重 + 悬停浅底，弥补 text 形态的弱可点感 */
.table-fill :deep(.cell-actions__btn) {
  font-weight: 500;
  padding: 2px 4px;
  border-radius: 4px;
  transition: background-color 0.15s ease;
}
.table-fill :deep(.cell-actions__btn:hover) {
  background: var(--app-muted-bg);
}
@media (max-width: 700px) {
  .pager {
    justify-content: center;
  }
}
/* FPS 导入弹窗：文件选择行 + 结果逐题列表（限高滚动） */
.import-fps {
  display: grid;
  gap: 12px;
}
.import-fps__hint {
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}
.import-fps__picker {
  display: flex;
  align-items: center;
  gap: 10px;
}
.import-fps__input {
  display: none;
}
.import-fps__file {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--app-text);
  font-size: 13px;
}
/* 开始导入与选择文件同行，右对齐 */
.import-fps__start {
  margin-left: auto;
}
.import-fps__summary {
  margin-top: 4px;
}
.import-fps__selected {
  margin: 0;
  color: var(--app-text);
  font-size: 13px;
}
.import-fps__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.import-fps__results {
  max-height: 260px;
  overflow: auto;
  display: grid;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--app-border);
  border-radius: 6px;
  background: var(--app-muted-bg);
}
.import-fps__row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.import-fps__title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.import-fps__msg {
  color: var(--app-text-secondary);
  font-size: 12px;
  max-width: 45%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
