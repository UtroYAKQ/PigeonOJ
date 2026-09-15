<script setup lang="ts">
/**
 * 组织管理（管理后台，admin；docs/contracts/orgs.md 管理端视图）：
 * 全量组织列表（含已解散）+ 创建组织入口（可同时任命初始组织管理员）；
 * 行整行点击进入组织详情（信息 / 成员 / 名下团队只读浏览）。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { CirclePlus } from '@element-plus/icons-vue'
import { NButton, NIcon, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import { adminListOrgs } from '@/api/admin'
import { createOrg } from '@/api/orgs'
import BaseAvatar from '@/components/BaseAvatar.vue'
import ModalFooter from '@/components/ModalFooter.vue'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { formatDateTime } from '@/utils/format'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import type { OrgDetail } from '@/types'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const list = ref<OrgDetail[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()
const keyword = ref('')
const statusFilter = ref<'active' | 'disbanded' | null>(null)

async function load() {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await adminListOrgs({
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
  { label: t('admin.orgs.statusActive'), value: 'active' },
  { label: t('admin.orgs.statusDisbanded'), value: 'disbanded' },
])
const statusValue = computed({
  get: () => statusFilter.value ?? 'all',
  set: (v: string) => {
    statusFilter.value = v === 'all' ? null : (v as 'active' | 'disbanded')
    onSearch()
  },
})

const columns = computed<DataTableColumns<OrgDetail>>(() => [
  {
    title: t('admin.orgs.avatar'),
    key: 'avatar_url',
    width: 72,
    align: 'center',
    render(row) {
      return h(BaseAvatar, { src: row.avatar_url, name: row.name, size: 36, kind: 'team' })
    },
  },
  {
    title: t('admin.orgs.org'),
    key: 'name',
    minWidth: 200,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'cell-name' }, row.name),
  },
  {
    title: t('admin.orgs.description'),
    key: 'description',
    minWidth: 180,
    ellipsis: { tooltip: true },
    render: (row) => row.description ?? '—',
  },
  {
    title: t('admin.orgs.memberCount'),
    key: 'member_count',
    width: 80,
    align: 'center',
    render: (row) => String(row.member_count),
  },
  {
    title: t('admin.orgs.teamCount'),
    key: 'team_count',
    width: 80,
    align: 'center',
    render: (row) => String(row.team_count),
  },
  {
    title: t('admin.orgs.status'),
    key: 'status',
    width: 96,
    render(row) {
      const active = row.status === 'active'
      return h(
        NTag,
        { size: 'small', bordered: false, type: active ? 'success' : 'error' },
        { default: () => t(active ? 'admin.orgs.statusActive' : 'admin.orgs.statusDisbanded') },
      )
    },
  },
  {
    title: t('admin.orgs.createdAt'),
    key: 'created_at',
    width: 170,
    render: (row) => formatDateTime(row.created_at),
  },
])

/** 编辑 / 成员维护在组织空间完成；管理端整行点击进入只读详情 */
function rowProps(row: OrgDetail) {
  return { style: 'cursor: pointer;', onClick: () => router.push(`/admin/orgs/${row.id}`) }
}

// ---- 创建组织（POST /orgs；可选批量任命初始组织管理员） ----

const showCreate = ref(false)
const creating = ref(false)
const createForm = ref({ name: '', description: '', adminIds: '' })

function openCreate() {
  createForm.value = { name: '', description: '', adminIds: '' }
  showCreate.value = true
}

async function doCreate() {
  if (!createForm.value.name.trim()) {
    message.warning(t('orgs.create.nameRequired'))
    return
  }
  const adminUserIds = createForm.value.adminIds
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
  creating.value = true
  try {
    const org = await createOrg({
      name: createForm.value.name.trim(),
      description: createForm.value.description.trim() || undefined,
      admin_user_ids: adminUserIds.length ? adminUserIds : undefined,
    })
    message.success(t('admin.orgs.createSuccess'))
    showCreate.value = false
    void router.push(`/admin/orgs/${org.id}`)
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
      :placeholder="t('admin.orgs.search')"
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
        :aria-label="t('admin.orgs.status')"
      />
      <template #actions>
        <n-button type="primary" size="small" @click="openCreate">
          <template #icon>
            <n-icon :component="CirclePlus" />
          </template>
          {{ t('admin.orgs.create') }}
        </n-button>
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
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
      :page-sizes="[20, 50, 100]"
      :empty-text="t('admin.orgs.empty')"
      :table-props="{ rowProps, scrollX: 1000 }"
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
        <span class="pager__total">{{ t('admin.orgs.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedDataTable>

    <!-- 创建组织：name ≤64 全站唯一；初始组织管理员为可选 UUID 列表 -->
    <n-modal
      v-model:show="showCreate"
      :title="t('admin.orgs.create')"
      preset="card"
      style="width: 480px"
    >
      <n-form label-placement="top">
        <n-form-item :label="t('orgs.create.name')" required>
          <n-input
            v-model:value="createForm.name"
            maxlength="64"
            :placeholder="t('orgs.create.namePlaceholder')"
          />
        </n-form-item>
        <n-form-item :label="t('orgs.create.description')">
          <n-input
            v-model:value="createForm.description"
            type="textarea"
            :rows="3"
            maxlength="2000"
            :placeholder="t('orgs.create.descriptionPlaceholder')"
          />
        </n-form-item>
        <n-form-item :label="t('orgs.create.adminIds')">
          <n-input
            v-model:value="createForm.adminIds"
            type="textarea"
            :rows="3"
            :placeholder="t('orgs.create.adminIdsPlaceholder')"
          />
          <span class="field-hint">{{ t('orgs.create.adminIdsHint') }}</span>
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
.field-hint {
  color: var(--app-text-secondary);
  font-size: 12px;
  margin-top: 4px;
}
</style>
