<script setup lang="ts">
import { computed, h, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { adminListOnlineUsers } from '@/api/admin'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { ROLE_NAME, USER_STATUS } from '@/constants/dict'
import { usePagination } from '@/composables/usePagination'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { GlobalRoleCode, OnlineUser } from '@/types'

const { t } = useI18n()

const loading = ref(false)
const rows = ref<OnlineUser[]>([])
const keyword = ref('')
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()

async function load(options: { silent?: boolean } = {}): Promise<void> {
  const seq = beginLoad()
  if (!options.silent) loading.value = true
  try {
    const result = await adminListOnlineUsers({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value.trim() || undefined,
    })
    if (!isCurrent(seq)) return
    rows.value = result.items
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

// 15s 轮询；页面隐藏时跳过，KeepAlive 失活（切到其他页）时暂停、激活后恢复。
let timer: ReturnType<typeof setInterval> | null = null
let active = false

function stopTimer(): void {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function startTimer(): void {
  stopTimer()
  timer = setInterval(() => {
    if (document.visibilityState === 'visible') void load({ silent: true })
  }, 15000)
}

onMounted(() => {
  active = true
  void load()
  startTimer()
})

onActivated(() => {
  if (!active) {
    active = true
    void load({ silent: true })
  }
  startTimer()
})

onDeactivated(() => {
  active = false
  stopTimer()
})

onBeforeUnmount(() => {
  active = false
  stopTimer()
})

function roleLabel(role: string | null): string {
  if (!role) return '—'
  return ROLE_NAME[role as GlobalRoleCode] ?? role
}

const columns = computed<AppTableColumn<OnlineUser>[]>(() => [
  {
    key: 'avatar_url',
    title: t('admin.online.avatar'),
    width: '64px',
    align: 'center',
    cell: (row) => h(BaseAvatar, { src: row.avatar_url, name: row.nickname, size: 32 }),
  },
  {
    key: 'nickname',
    title: t('admin.online.user'),
    width: '140px',
    cell: (row) => h('span', { class: 'font-medium' }, row.nickname || '—'),
  },
  {
    key: 'email',
    title: t('admin.users.email'),
    cell: (row) => h('span', { class: 'text-[12.5px] text-muted-foreground' }, row.email),
  },
  {
    key: 'role',
    title: t('admin.users.role'),
    width: '110px',
    cell: (row) => roleLabel(row.role),
  },
  {
    key: 'status',
    title: t('admin.users.status'),
    width: '90px',
    cell: (row) => {
      const meta = USER_STATUS[row.status as keyof typeof USER_STATUS]
      return h(ToneBadge, {
        tone: meta?.tag ?? 'info',
        label: meta?.label ?? row.status,
      })
    },
  },
  {
    key: 'device_info',
    title: t('admin.online.device'),
    width: '170px',
    cell: (row) => row.device_info ?? t('common.unknownDevice'),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'ip_address',
    title: t('admin.online.ip'),
    cell: (row) => {
      const ip = row.ip_address ?? '--'
      return row.location ? `${ip} · ${row.location}` : ip
    },
    cellClass: 'text-[12.5px] text-muted-foreground tabular-nums',
  },
  {
    key: 'session_created_at',
    title: t('sessions.loginAt'),
    width: '150px',
    cell: (row) => formatDateTime(row.session_created_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'last_active_at',
    title: t('sessions.lastActive'),
    width: '150px',
    cell: (row) => formatDateTime(row.last_active_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
])
</script>

<template>
  <WorkbenchShell :title="t('nav.onlineUsers')">
    <template #toolbar>
      <SearchFilterBar
        :keyword="keyword"
        :placeholder="t('admin.online.search')"
        @update:keyword="keyword = $event"
        @search="onSearch"
        @reset="onSearch"
      >
        <template #actions>
          <ToneBadge tone="success" :label="t('admin.online.summary', { count: total })" />
          <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load()" />
        </template>
      </SearchFilterBar>
    </template>

    <PaginatedTable
      :columns="columns"
      :data="rows"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      show-size-picker
      :empty-text="t('admin.online.empty')"
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
  </WorkbenchShell>
</template>
