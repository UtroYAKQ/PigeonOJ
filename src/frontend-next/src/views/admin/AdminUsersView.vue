<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { VNode } from 'vue'

import { adminListUsers, adminUnbanUser, adminUnfreezeUser } from '@/api/admin'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { USER_STATUS, ROLE_NAME } from '@/constants/dict'
import { usePagination } from '@/composables/usePagination'
import { confirmDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import UserReasonDialog from './user-components/UserReasonDialog.vue'
import UserRoleDialog from './user-components/UserRoleDialog.vue'
import type { User, UserStatus } from '@/types'

const { t } = useI18n()

const loading = ref(false)
const list = ref<User[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()

const query = reactive({
  keyword: '',
  status: 'all' as UserStatus | 'all',
})

const statusOptions = computed(() =>
  (['active', 'frozen', 'banned'] as UserStatus[]).map((value) => ({
    value,
    label: USER_STATUS[value].label,
  })),
)

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await adminListUsers({
      page: page.value,
      page_size: pageSize.value,
      keyword: query.keyword || undefined,
      status: query.status === 'all' ? undefined : query.status,
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

function onSearch(): void {
  resetPage()
  void load()
}

// ---- 角色设置 ----
const roleOpen = ref(false)
const roleTarget = ref<User | null>(null)

function openRole(user: User): void {
  roleTarget.value = user
  roleOpen.value = true
}

// ---- 封禁 / 冻结 ----
const reasonOpen = ref(false)
const reasonAction = ref<'ban' | 'freeze'>('ban')
const reasonTarget = ref<User | null>(null)

function openReason(action: 'ban' | 'freeze', user: User): void {
  reasonAction.value = action
  reasonTarget.value = user
  reasonOpen.value = true
}

async function confirmState(action: 'unban' | 'unfreeze', user: User): Promise<void> {
  const ok = await confirmDialog({
    title: t(`admin.users.${action}`),
    content: t(action === 'unban' ? 'admin.users.confirmUnban' : 'admin.users.confirmUnfreeze', {
      name: user.nickname,
    }),
    positiveText: t('action.confirm'),
    negativeText: t('action.cancel'),
  })
  if (!ok) return
  try {
    await (action === 'unban' ? adminUnbanUser(user.id) : adminUnfreezeUser(user.id))
    message.success(t('common.success'))
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

function roleCell(row: User): VNode | string {
  const roles = row.roles ?? []
  if (!roles.length) return '—'
  return h(
    'div',
    { class: 'flex flex-wrap gap-1' },
    roles.map((role) =>
      h(
        Badge,
        {
          variant: 'outline',
          class: 'h-5 px-2 text-[11.5px] font-normal text-muted-foreground',
        },
        { default: () => ROLE_NAME[role] ?? role },
      ),
    ),
  )
}

function statusCell(row: User): VNode {
  const meta = USER_STATUS[row.status] ?? { label: row.status, tag: 'info' as const }
  const badge = h(ToneBadge, { tone: meta.tag, label: meta.label })
  if (row.status === 'frozen' && row.frozen_until) {
    return h(
      'span',
      { title: `${t('admin.users.freezeUntil')} ${formatDateTime(row.frozen_until)}` },
      [badge],
    )
  }
  return badge
}

function actionCell(row: User): VNode {
  const buttons: VNode[] = [
    h(
      Button,
      { variant: 'ghost', size: 'xs', onClick: () => openRole(row) },
      { default: () => t('admin.users.role') },
    ),
  ]
  if (row.status === 'banned') {
    buttons.push(
      h(
        Button,
        {
          variant: 'ghost',
          size: 'xs',
          class: 'text-emerald-600 hover:text-emerald-600 dark:text-emerald-400',
          onClick: () => confirmState('unban', row),
        },
        { default: () => t('admin.users.unban') },
      ),
    )
  } else if (row.status === 'frozen') {
    buttons.push(
      h(
        Button,
        {
          variant: 'ghost',
          size: 'xs',
          class: 'text-emerald-600 hover:text-emerald-600 dark:text-emerald-400',
          onClick: () => confirmState('unfreeze', row),
        },
        { default: () => t('admin.users.unfreeze') },
      ),
    )
  } else if (row.status === 'active') {
    buttons.push(
      h(
        Button,
        { variant: 'ghost', size: 'xs', onClick: () => openReason('freeze', row) },
        { default: () => t('admin.users.freeze') },
      ),
      h(
        Button,
        {
          variant: 'ghost',
          size: 'xs',
          class: 'text-destructive hover:text-destructive',
          onClick: () => openReason('ban', row),
        },
        { default: () => t('admin.users.ban') },
      ),
    )
  }
  return h('div', { class: 'flex items-center justify-end gap-1' }, buttons)
}

const columns = computed<AppTableColumn<User>[]>(() => [
  {
    key: 'avatar_url',
    title: t('admin.users.avatar'),
    width: '64px',
    align: 'center',
    cell: (row) => h(BaseAvatar, { src: row.avatar_url, name: row.nickname, size: 32 }),
  },
  {
    key: 'nickname',
    title: t('admin.users.user'),
    width: '150px',
    cell: (row) => h('span', { class: 'font-medium' }, row.nickname || '—'),
  },
  {
    key: 'email',
    title: t('admin.users.email'),
    cell: (row) => h('span', { class: 'text-[12.5px] text-muted-foreground' }, row.email),
  },
  {
    key: 'roles',
    title: t('admin.users.role'),
    width: '160px',
    cell: roleCell,
  },
  {
    key: 'status',
    title: t('admin.users.status'),
    width: '90px',
    cell: statusCell,
  },
  {
    key: 'last_login_at',
    title: t('admin.users.lastLogin'),
    width: '150px',
    cell: (row) => formatDateTime(row.last_login_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'created_at',
    title: t('admin.users.registered'),
    width: '150px',
    cell: (row) => formatDateTime(row.created_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'actions',
    title: t('action.edit'),
    width: '210px',
    align: 'right',
    cell: actionCell,
  },
])

onMounted(load)
</script>

<template>
  <WorkbenchShell :title="t('nav.users')">
    <template #toolbar>
      <SearchFilterBar
        :keyword="query.keyword"
        :placeholder="t('admin.users.search')"
        @update:keyword="query.keyword = $event"
        @search="onSearch"
        @reset="onSearch"
      >
        <Select
          :model-value="query.status"
          @update:model-value="
            (value) => {
              query.status = String(value) as UserStatus | 'all'
              onSearch()
            }
          "
        >
          <SelectTrigger class="h-9 w-[140px] text-[13px]">
            <SelectValue :placeholder="t('common.allStatus')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('common.allStatus') }}</SelectItem>
            <SelectItem v-for="option in statusOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </SelectItem>
          </SelectContent>
        </Select>
        <template #actions>
          <RefreshButton :loading="loading" :label="t('action.refresh')" @click="onSearch" />
        </template>
      </SearchFilterBar>
    </template>

    <PaginatedTable
      :columns="columns"
      :data="list"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :page-sizes="[10, 20, 50]"
      show-size-picker
      :empty-text="t('admin.users.empty')"
      @update:page="
        (value: number) => {
          changePage(value)
          load()
        }
      "
      @update:page-size="
        (value: number) => {
          changeSize(value)
          load()
        }
      "
    />

    <UserRoleDialog v-model:open="roleOpen" :user="roleTarget" @saved="load" />
    <UserReasonDialog
      v-model:open="reasonOpen"
      :action="reasonAction"
      :user="reasonTarget"
      @done="load"
    />
  </WorkbenchShell>
</template>
