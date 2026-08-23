<script setup lang="ts">
import { CirclePlus, Refresh, Search } from '@element-plus/icons-vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { listProblems } from '@/api/problems'
import { useUserStore } from '@/stores/user'
import type { PageResult, ProblemDifficulty, ProblemSummary } from '@/api/types'

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

function onSearch() {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => { page.value = 1; load() }, 300)
}
function changeDifficulty() { page.value = 1; load() }
function toggleMine() { page.value = 1; if (!mineOnly.value) statusFilter.value = ''; load() }
function changeStatus() { page.value = 1; load() }
function changePage(value: number) { page.value = value; load() }

watch(isLoggedIn, (v) => { if (!v) { mineOnly.value = false; load() } })

onMounted(load)
</script>
<template>
  <div class="problems-page">
    <header class="page-heading">
      <div>
        <p class="page-heading__eyebrow">{{ t('nav.problems') }}</p>
        <h1>{{ t('problems.list.title') }}</h1>
        <p>{{ t('problems.list.description') }}</p>
      </div>
      <div class="page-heading__actions">
        <el-button :icon="Refresh" :loading="loading" @click="load">{{ t('action.refresh') }}</el-button>
        <el-button type="primary" :icon="CirclePlus" @click="router.push('/problems/new')">{{ t('problems.list.create') }}</el-button>
      </div>
    </header>
    <el-card shadow="never" class="problems-card">
      <div class="problems-toolbar">
        <el-input v-model="keyword" :prefix-icon="Search" :placeholder="t('problems.list.name')" clearable class="problems-toolbar__search" @input="onSearch"/>
        <el-select v-model="difficulty" :placeholder="t('problems.list.difficulty')" clearable class="problems-toolbar__difficulty" @change="changeDifficulty">
          <el-option label="Easy" value="easy"/>
          <el-option label="Medium" value="medium"/>
          <el-option label="Hard" value="hard"/>
        </el-select>
        <el-select v-if="mineOnly" v-model="statusFilter" :placeholder="t('common.allStatus')" clearable class="problems-toolbar__difficulty" @change="changeStatus">
          <el-option :label="t('problems.list.statusDraft')" value="draft"/>
          <el-option :label="t('problems.list.statusPublished')" value="published"/>
          <el-option :label="t('problems.list.statusArchived')" value="archived"/>
        </el-select>
        <el-checkbox v-if="isLoggedIn" v-model="mineOnly" class="problems-toolbar__mine" @change="toggleMine">{{ t('problems.list.mineOnly') }}</el-checkbox>
      </div>
      <el-table v-loading="loading" :data="problems" class="problems-table" @row-click="(row: ProblemSummary) => router.push(`/problems/${row.id}`)">
        <el-table-column prop="title" :label="t('problems.list.name')" min-width="280">
          <template #default="{ row }">
            <div class="problem-name">
              <strong>{{ row.title }}</strong>
              <span>#{{ row.id.slice(0, 8) }}<template v-if="mineOnly"> · {{ row.visibility }}</template><template v-else-if="row.status !== 'published'"> · {{ row.status }}</template></span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="difficulty" :label="t('problems.list.difficulty')" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="row.difficulty === 'hard' ? 'danger' : row.difficulty === 'medium' ? 'warning' : 'success'" effect="light">{{ row.difficulty }}</el-tag>
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
      <div v-if="total > pageSize" class="problems-pagination">
        <el-pagination background layout="prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="changePage"/>
      </div>
    </el-card>
  </div>
</template>
<style scoped>.problems-page{display:grid;gap:20px}.page-heading{display:flex;align-items:end;justify-content:space-between;gap:16px}.page-heading__eyebrow{margin:0 0 6px;color:var(--el-color-primary);font-size:11px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.page-heading h1{margin:0;font-size:26px;letter-spacing:-.035em}.page-heading p:not(.page-heading__eyebrow){margin:8px 0 0;color:var(--app-text-muted);font-size:13px}.page-heading__actions{display:flex;gap:10px;flex-wrap:wrap}.problems-toolbar{display:flex;justify-content:space-between;gap:12px;margin-bottom:18px}.problems-toolbar__search{width:300px}.problems-toolbar__difficulty{width:150px}.problems-toolbar__mine{margin-left:auto}.problems-table :deep(.el-table__row){cursor:pointer}.problem-name{display:grid;gap:4px}.problem-name strong{font-size:14px}.problem-name span,.problems-table__muted{color:var(--app-text-muted);font-size:12px}.problems-pagination{display:flex;justify-content:end;margin-top:16px}@media(max-width:600px){.page-heading{align-items:start;flex-direction:column}.page-heading__actions{width:100%}.page-heading__actions .el-button{flex:1}.problems-toolbar{flex-direction:column}.problems-toolbar__search,.problems-toolbar__difficulty{width:100%}}</style>
