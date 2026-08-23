<script setup lang="ts">
import { CirclePlus, Refresh, Search } from '@element-plus/icons-vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { listProblems } from '@/api/problems'
import { useUserStore } from '@/stores/user'
import type { PageResult, ProblemDifficulty, ProblemSummary } from '@/types'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()
const loading = ref(false)
const problems = ref<ProblemSummary[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const difficulty = ref<'' | ProblemDifficulty>('')
const mineOnly = ref(false)
const statusFilter = ref<'' | 'draft' | 'published' | 'archived'>('')
let searchTimer: number | undefined

const isLoggedIn = computed(() => userStore.isLoggedIn)
const statusLabelKey: Record<string, string> = {
  draft: 'problems.list.statusDraft',
  published: 'problems.list.statusPublished',
  archived: 'problems.list.statusArchived',
}

async function load() {
  loading.value = true
  try {
    const result: PageResult<ProblemSummary> = await listProblems({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      difficulty: difficulty.value || undefined,
      scope: mineOnly.value ? 'mine' : undefined,
      status: statusFilter.value || undefined,
    })
    problems.value = result.items
    total.value = result.total
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : t('problems.list.loadFailed'))
  } finally {
    loading.value = false
  }
}

function scheduleSearch() {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => { page.value = 1; load() }, 300)
}

// 中文输入法组词过程不触发搜索（compositionend 后再统一触发）
let composing = false
function onKeywordInput() {
  if (composing) return
  scheduleSearch()
}
function onCompositionStart() { composing = true }
function onCompositionEnd() {
  composing = false
  scheduleSearch()
}

function changeDifficulty() { page.value = 1; load() }
function toggleMine() { page.value = 1; if (!mineOnly.value) statusFilter.value = ''; load() }
function changeStatus() { page.value = 1; load() }
function changePage(value: number) { page.value = value; load() }
function changeSize(value: number) { pageSize.value = value; page.value = 1; load() }

watch(isLoggedIn, (v) => { if (!v) { mineOnly.value = false; load() } })

onMounted(load)
</script>

<template>
  <div class="problems-page page-stack">
    <el-card shadow="never" class="problems-card">
      <div class="problems-toolbar">
        <el-input
          v-model="keyword"
          :prefix-icon="Search"
          :placeholder="t('problems.list.name')"
          clearable
          class="problems-toolbar__search"
          @input="onKeywordInput"
          @compositionstart="onCompositionStart"
          @compositionend="onCompositionEnd"
        />
        <el-select v-model="difficulty" :placeholder="t('problems.list.difficulty')" clearable class="problems-toolbar__difficulty" @change="changeDifficulty">
          <el-option :label="t('problems.difficulty.easy')" value="easy"/>
          <el-option :label="t('problems.difficulty.medium')" value="medium"/>
          <el-option :label="t('problems.difficulty.hard')" value="hard"/>
        </el-select>
        <el-select v-if="mineOnly" v-model="statusFilter" :placeholder="t('common.allStatus')" clearable class="problems-toolbar__difficulty" @change="changeStatus">
          <el-option :label="t('problems.list.statusDraft')" value="draft"/>
          <el-option :label="t('problems.list.statusPublished')" value="published"/>
          <el-option :label="t('problems.list.statusArchived')" value="archived"/>
        </el-select>
        <el-checkbox v-if="isLoggedIn" v-model="mineOnly" class="problems-toolbar__mine" @change="toggleMine">{{ t('problems.list.mineOnly') }}</el-checkbox>
        <div class="problems-toolbar__actions">
          <el-button :icon="Refresh" circle :loading="loading" :aria-label="t('action.refresh')" @click="load"/>
          <el-button type="primary" :icon="CirclePlus" @click="router.push('/problems/new')">{{ t('problems.list.create') }}</el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="problems" class="problems-table" @row-click="(row: ProblemSummary) => router.push(`/problems/${row.id}`)">
        <el-table-column prop="title" :label="t('problems.list.name')" min-width="280">
          <template #default="{ row }">
            <div class="problem-name">
              <strong>{{ row.title }}</strong>
              <span>#{{ (row.id || '').slice(0, 8) }}<template v-if="mineOnly"> · {{ t(`problems.visibility.${row.visibility}`) }}</template><template v-else-if="row.status !== 'published'"> · {{ t(statusLabelKey[row.status] ?? row.status) }}</template></span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="difficulty" :label="t('problems.list.difficulty')" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="row.difficulty === 'hard' ? 'danger' : row.difficulty === 'medium' ? 'warning' : 'success'" effect="light">{{ t(`problems.difficulty.${row.difficulty}`) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('problems.list.limits')" width="220">
          <template #default="{ row }">{{ row.time_limit_ms }} ms <span class="problems-table__muted">/</span> {{ row.memory_limit_mb }} MB</template>
        </el-table-column>
        <el-table-column :label="t('problems.list.type')" width="140">
          <template #default="{ row }"><el-tag size="small" :type="row.spj ? 'warning' : 'info'">{{ row.spj ? 'SPJ' : t('problems.list.standard') }}</el-tag></template>
        </el-table-column>
        <template #empty><el-empty :description="t('problems.list.empty')" :image-size="88"/></template>
      </el-table>

      <div class="problems-pagination">
        <span class="problems-pagination__total">{{ t('problems.list.totalCount', { count: total }) }}</span>
        <el-pagination
          background
          layout="prev, pager, next, sizes"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          :page-sizes="[20, 50, 100]"
          @current-change="changePage"
          @size-change="changeSize"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.problems-toolbar { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 18px; flex-wrap: wrap; }
.problems-toolbar__search { width: 300px; }
.problems-toolbar__difficulty { width: 150px; }
.problems-toolbar__mine { margin: 0; }
.problems-toolbar__actions { margin-left: auto; display: flex; align-items: center; gap: 10px; }
.problems-table :deep(.el-table__row) { cursor: pointer; }
.problem-name { display: grid; gap: 4px; }
.problem-name strong { font-size: 14px; }
.problem-name span, .problems-table__muted { color: var(--app-text-muted); font-size: 12px; }

/* 分页常驻：总数 + 页容量始终可见（此前 total ≤ pageSize 时整块消失） */
.problems-pagination { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 16px; flex-wrap: wrap; }
.problems-pagination__total { color: var(--app-text-muted); font-size: 13px; }

@media (max-width: 600px) {
  .problems-toolbar { flex-direction: column; }
  .problems-toolbar__search, .problems-toolbar__difficulty { width: 100%; }
  .problems-toolbar__actions { margin-left: 0; }
  .problems-pagination { justify-content: center; }
}
</style>
