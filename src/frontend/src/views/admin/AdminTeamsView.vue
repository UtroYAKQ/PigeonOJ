<script setup lang="ts">
/**
 * 团队管理（管理后台，admin；docs/contracts/teams.md 管理端）：
 * 全量团队列表（含已解散）+ 创建团队入口（创建动作自前台团队中心收敛到后台）；
 * 行整行点击进入团队详情（成员 / 团队题库 / 团队题单 / 团队比赛只读浏览）。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { CirclePlus } from '@element-plus/icons-vue'
import { NAvatar, NButton, NIcon, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import { adminListTeams } from '@/api/admin'
import { createTeam } from '@/api/teams'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { formatDateTime } from '@/utils/format'
import ModalFooter from '@/components/ModalFooter.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import type { TeamAdminSummary } from '@/types'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const list = ref<TeamAdminSummary[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()
const keyword = ref('')
const statusFilter = ref<'active' | 'disbanded' | null>(null)

async function load() {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await adminListTeams({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      status: statusFilter.value ?? undefined,
    })
    if (!isCurrent(seq)) return
    list.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

function onSearch() {
  resetPage()
  load()
}

onMounted(load)

const statusOptions = computed(() => [
  { label: t('common.allStatus'), value: 'all' },
  { label: t('admin.teams.statusActive'), value: 'active' },
  { label: t('admin.teams.statusDisbanded'), value: 'disbanded' },
])
const statusValue = computed({
  get: () => statusFilter.value ?? 'all',
  set: (v: string) => {
    statusFilter.value = v === 'all' ? null : (v as 'active' | 'disbanded')
    onSearch()
  },
})

function initialOf(team: TeamAdminSummary) {
  return team.name?.trim()?.charAt(0).toUpperCase() || 'T'
}

const columns = computed<DataTableColumns<TeamAdminSummary>>(() => [
  {
    // 头像独立一列（圆形 36px），与名称列拉开间距
    title: t('admin.teams.avatar'),
    key: 'avatar_url',
    width: 72,
    align: 'center',
    render(row) {
      return h(NAvatar, { size: 36, round: true, src: row.avatar_url || undefined }, row.avatar_url ? {} : { default: () => initialOf(row) })
    },
  },
  {
    title: t('admin.teams.team'),
    key: 'name',
    minWidth: 200,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'cell-name' }, row.name),
  },
  {
    title: t('admin.teams.creator'),
    key: 'creator_nickname',
    width: 140,
    ellipsis: { tooltip: true },
    render: (row) => row.creator_nickname ?? '—',
  },
  {
    title: t('admin.teams.memberCount'),
    key: 'member_count',
    width: 80,
    align: 'center',
    render: (row) => String(row.member_count),
  },
  {
    title: t('admin.teams.statProblems'),
    key: 'problem_count',
    width: 90,
    align: 'center',
    render: (row) => String(row.problem_count),
  },
  {
    title: t('admin.teams.statSets'),
    key: 'problem_set_count',
    width: 70,
    align: 'center',
    render: (row) => String(row.problem_set_count),
  },
  {
    title: t('admin.teams.statContests'),
    key: 'contest_count',
    width: 70,
    align: 'center',
    render: (row) => String(row.contest_count),
  },
  {
    title: t('admin.teams.status'),
    key: 'status',
    width: 96,
    render(row) {
      const active = row.status === 'active'
      return h(
        NTag,
        { size: 'small', bordered: false, type: active ? 'success' : 'error' },
        { default: () => t(active ? 'admin.teams.statusActive' : 'admin.teams.statusDisbanded') },
      )
    },
  },
  {
    title: t('admin.teams.createdAt'),
    key: 'created_at',
    width: 170,
    render: (row) => formatDateTime(row.created_at),
  },
])

/** 编辑 / 成员维护在团队空间完成；管理端整行点击进入只读详情 */
function rowProps(row: TeamAdminSummary) {
  return { style: 'cursor: pointer;', onClick: () => router.push(`/admin/teams/${row.id}`) }
}

// ---- 创建团队（自前台团队中心收敛到后台；POST /teams 权限仍为 admin/tutor） ----

const showCreate = ref(false)
const creating = ref(false)
const createForm = ref({ name: '', description: '' })

function openCreate() {
  createForm.value = { name: '', description: '' }
  showCreate.value = true
}

async function doCreate() {
  if (!createForm.value.name.trim()) {
    message.warning(t('teams.create.nameRequired'))
    return
  }
  creating.value = true
  try {
    const team = await createTeam({
      name: createForm.value.name.trim(),
      description: createForm.value.description.trim() || undefined,
    })
    message.success(t('admin.teams.createSuccess'))
    showCreate.value = false
    void router.push(`/admin/teams/${team.id}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <WorkbenchShell>
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('admin.teams.search')"
      search-width="260px"
      manual
      @update:keyword="
        (v: string) => {
          keyword = v
        }
      "
      @search="onSearch"
      @reset="onSearch"
    >
      <n-select
        v-model:value="statusValue"
        style="width: 130px"
        :options="statusOptions"
        :aria-label="t('admin.teams.status')"
      />
      <template #actions>
        <n-button type="primary" size="small" @click="openCreate">
          <template #icon>
            <n-icon :component="CirclePlus" />
          </template>
          {{ t('admin.teams.create') }}
        </n-button>
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <PaginatedDataTable
      :columns="columns"
      :data="list"
      :loading="loading"
      :total="total"
      v-model:page="page"
      v-model:page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      :empty-text="t('admin.teams.empty')"
      :table-props="{ rowProps, scrollX: 1100 }"
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
        <span class="pager__total">{{ t('admin.teams.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedDataTable>

    <!-- 创建团队（表单与前台原创建弹窗一致：name ≤64 / description ≤2000） -->
    <n-modal
      v-model:show="showCreate"
      :title="t('admin.teams.create')"
      preset="card"
      style="width: 480px"
    >
      <n-form label-placement="top">
        <n-form-item :label="t('teams.create.name')" required>
          <n-input
            v-model:value="createForm.name"
            maxlength="64"
            :placeholder="t('teams.create.namePlaceholder')"
          />
        </n-form-item>
        <n-form-item :label="t('teams.create.description')">
          <n-input
            v-model:value="createForm.description"
            type="textarea"
            :rows="3"
            maxlength="2000"
            :placeholder="t('teams.create.descriptionPlaceholder')"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <ModalFooter
          :loading="creating"
          :confirm-text="t('action.save')"
          @cancel="showCreate = false"
          @confirm="doCreate"
        />
      </template>
    </n-modal>
  </WorkbenchShell>
</template>

<style scoped>
.cell-name {
  font-weight: 600;
  color: var(--app-text);
}
</style>
