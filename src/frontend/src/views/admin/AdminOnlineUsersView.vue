<script setup lang="ts">
/**
 * 在线用户面板（/admin/users/online）：10 分钟窗口内有活跃回写的有效会话。
 * 同设备去重下每行 = 一台在线设备；数据随刷新按钮 / 15s 轮询更新（页面隐藏时暂停）。
 */
import { computed, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NAvatar, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import * as adminApi from '@/api/admin'
import type { OnlineUser } from '@/types'
import { ROLE_NAME, USER_STATUS, toNaiveTagType } from '@/constants/dict'
import { formatDateTime } from '@/utils/format'
import RefreshButton from '@/components/RefreshButton.vue'
import { message } from '@/utils/feedback'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'

const { t } = useI18n()
const loading = ref(false)
const rows = ref<OnlineUser[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const res = await adminApi.adminListOnlineUsers({
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = res.items
    total.value = res.total
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}
function reload() {
  page.value = 1
  load()
}

// 15s 轮询；页面隐藏时暂停（后台标签页不白耗请求）
let timer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  load()
  timer = setInterval(() => {
    if (document.visibilityState === 'visible') void load()
  }, 15000)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})

const columns = computed<DataTableColumns<OnlineUser>>(() => [
  {
    title: t('admin.online.avatar'),
    key: 'avatar_url',
    width: 70,
    align: 'center',
    render(row) {
      return h(
        NAvatar,
        { size: 32, round: true, src: row.avatar_url || undefined },
        row.avatar_url ? {} : { default: () => (row.nickname ?? '?').slice(0, 1) },
      )
    },
  },
  {
    title: t('admin.online.user'),
    key: 'nickname',
    minWidth: 130,
    ellipsis: { tooltip: true },
    render: (row) => row.nickname ?? '—',
  },
  {
    title: t('admin.users.email'),
    key: 'email',
    minWidth: 180,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'cell-email' }, row.email),
  },
  {
    title: t('admin.users.role'),
    key: 'role',
    width: 110,
    render: (row) => (row.role ? (ROLE_NAME[row.role as keyof typeof ROLE_NAME] ?? row.role) : '—'),
  },
  {
    title: t('admin.users.status'),
    key: 'status',
    width: 90,
    render(row) {
      const meta = USER_STATUS[row.status as keyof typeof USER_STATUS]
      return h(
        NTag,
        { size: 'small', type: toNaiveTagType(meta?.tag ?? 'info'), bordered: false },
        { default: () => meta?.label ?? row.status },
      )
    },
  },
  {
    title: t('admin.online.device'),
    key: 'device_info',
    minWidth: 150,
    ellipsis: { tooltip: true },
    render: (row) => row.device_info ?? t('common.unknownDevice'),
  },
  {
    title: t('admin.online.ip'),
    key: 'ip_address',
    minWidth: 220,
    render(row) {
      const ip = row.ip_address ?? '--'
      return row.location ? `${ip} · ${row.location}` : ip
    },
  },
  {
    title: t('sessions.loginAt'),
    key: 'session_created_at',
    width: 160,
    render: (row) => formatDateTime(row.session_created_at),
  },
  {
    title: t('sessions.lastActive'),
    key: 'last_active_at',
    width: 160,
    render: (row) => formatDateTime(row.last_active_at),
  },
])
</script>

<template>
  <WorkbenchShell>
    <template #header>
      <n-tag type="success" :bordered="false" round>
        {{ t('admin.online.summary', { count: total }) }}
      </n-tag>
    </template>
    <template #header-extra>
      <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
    </template>

    <PaginatedDataTable
      show-size-picker
      :columns="columns"
      :data="rows"
      :loading="loading"
      :total="total"
      v-model:page="page"
      v-model:page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      :empty-text="t('admin.online.empty')"
      :table-props="{ scrollX: 1100 }"
      @update:page="
        (p: number) => {
          page = p
          load()
        }
      "
      @update:page-size="
        (s: number) => {
          pageSize = s
          reload()
        }
      "
    />
  </WorkbenchShell>
</template>

<style scoped>
.cell-email {
  color: var(--app-text-secondary);
}
</style>
