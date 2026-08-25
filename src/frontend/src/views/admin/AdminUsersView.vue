<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NAvatar, NButton, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import * as adminApi from '@/api/admin'
import type { GlobalRoleCode, User, UserStatus } from '@/types'
import { ROLE_NAME, USER_STATUS, toNaiveTagType } from '@/constants/dict'
import { formatDateTime } from '@/utils/format'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import ModalFooter from '@/components/ModalFooter.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'

const { t } = useI18n()
const loading = ref(false)
const list = ref<User[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage } = usePagination()
const query = reactive({
  keyword: '',
  status: '' as UserStatus | '',
})
const roleModal = ref(false)
const roleTarget = ref<User | null>(null)
const roleIds = ref<GlobalRoleCode[]>([])
const roleSaving = ref(false)

/** 封禁 / 冻结原因弹窗（可选输入，替代原 prompt） */
const reasonVisible = ref(false)
const reasonAction = ref<'ban' | 'freeze'>('ban')
const reasonTarget = ref<User | null>(null)
const reasonText = ref('')
const reasonSubmitting = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await adminApi.adminListUsers({
      page: page.value,
      page_size: pageSize.value,
      keyword: query.keyword,
      status: query.status,
    })
    list.value = res.items
    total.value = res.total
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}
onMounted(load)
function onSearch() {
  resetPage()
  load()
}
function onReset() {
  query.keyword = ''
  query.status = ''
  resetPage()
  load()
}

const statusOptions = computed(() => [
  { label: t('user.status.active'), value: 'active' },
  { label: t('user.status.frozen'), value: 'frozen' },
  { label: t('user.status.banned'), value: 'banned' },
])

const roleOptions = computed(() =>
  (Object.keys(ROLE_NAME) as GlobalRoleCode[]).map((code) => ({
    label: ROLE_NAME[code],
    value: code,
  })),
)

function openRoleDialog(user: User) {
  roleTarget.value = user
  roleIds.value = [...(user.roles ?? [])]
  roleModal.value = true
}
async function saveRoles() {
  if (!roleTarget.value) return
  if (!roleIds.value.length) {
    message.warning(t('admin.users.keepRole'))
    return
  }
  roleSaving.value = true
  try {
    await adminApi.adminSetRoles(roleTarget.value.id, roleIds.value)
    message.success(t('admin.users.rolesUpdated'))
    roleModal.value = false
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.updateFailed'))
  } finally {
    roleSaving.value = false
  }
}

/** 封禁 / 冻结：打开原因输入弹窗 */
function openReason(action: 'ban' | 'freeze', user: User) {
  reasonAction.value = action
  reasonTarget.value = user
  reasonText.value = ''
  reasonVisible.value = true
}
async function submitReason() {
  const action = reasonAction.value
  const user = reasonTarget.value
  if (!user) return
  if (reasonText.value.length > 255) {
    message.warning(t('admin.users.reasonTooLong'))
    return
  }
  reasonSubmitting.value = true
  try {
    if (action === 'ban') await adminApi.adminBanUser(user.id, reasonText.value)
    else await adminApi.adminFreezeUser(user.id, reasonText.value)
    message.success(t('common.success'))
    reasonVisible.value = false
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.operationFailed'))
  } finally {
    reasonSubmitting.value = false
  }
}

function confirmState(action: 'unban' | 'unfreeze', user: User) {
  confirmAsyncDialog({
    title: t(`admin.users.${action}`),
    content: t(
      action === 'unban' ? 'admin.users.confirmUnban' : 'admin.users.confirmUnfreeze',
      { name: user.nickname },
    ),
    positiveText: t('action.confirm'),
    action: () => action === 'unban' ? adminApi.adminUnbanUser(user.id) : adminApi.adminUnfreezeUser(user.id),
    successMessage: t('common.success'),
    onAfterSuccess: () => load(),
  })
}

const columns = computed<DataTableColumns<User>>(() => [
  {
    title: t('admin.users.user'),
    key: 'user',
    minWidth: 200,
    render(row) {
      return h('div', { class: 'cell-user' }, [
        h(
          NAvatar,
          { size: 32, round: true, src: row.avatar_url ?? undefined },
          { default: () => (row.nickname ?? '?').slice(0, 1) },
        ),
        h('div', { class: 'cell-user__meta' }, [
          h('div', null, row.nickname),
          h('div', { class: 'cell-user__email' }, row.email),
        ]),
      ])
    },
  },
  {
    title: t('admin.users.role'),
    key: 'roles',
    minWidth: 150,
    render(row) {
      const roles = row.roles ?? []
      if (!roles.length) return '—'
      return roles.map((r) =>
        h(
          NTag,
          { size: 'small', bordered: false, style: 'margin-right:4px' },
          { default: () => ROLE_NAME[r] ?? r },
        ),
      )
    },
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
    title: t('admin.users.lastLogin'),
    key: 'last_login_at',
    width: 150,
    render: (row) => formatDateTime(row.last_login_at),
  },
  {
    title: t('admin.users.registered'),
    key: 'created_at',
    width: 150,
    render: (row) => formatDateTime(row.created_at),
  },
  {
    title: t('action.edit'),
    key: 'actions',
    width: 220,
    fixed: 'right',
    render(row) {
      const buttons: ReturnType<typeof h>[] = [
        h(
          NButton,
          { text: true, type: 'primary', onClick: () => openRoleDialog(row) },
          { default: () => t('admin.users.role') },
        ),
      ]
      if (row.status === 'banned') {
        buttons.push(
          h(
            NButton,
            { text: true, type: 'success', onClick: () => confirmState('unban', row) },
            { default: () => t('admin.users.unban') },
          ),
        )
      } else if (row.status === 'frozen') {
        buttons.push(
          h(
            NButton,
            { text: true, type: 'success', onClick: () => confirmState('unfreeze', row) },
            { default: () => t('admin.users.unfreeze') },
          ),
        )
      } else if (row.status === 'active') {
        buttons.push(
          h(
            NButton,
            { text: true, type: 'warning', onClick: () => openReason('freeze', row) },
            { default: () => t('admin.users.freeze') },
          ),
          h(
            NButton,
            { text: true, type: 'error', onClick: () => openReason('ban', row) },
            { default: () => t('admin.users.ban') },
          ),
        )
      }
      return h('div', { class: 'cell-actions' }, buttons)
    },
  },
])
</script>

<template>
  <div class="page-fill">
    <n-card :title="t('admin.users.title')" :bordered="false">
    <SearchFilterBar
      :keyword="query.keyword"
      :placeholder="t('admin.users.search')"
      @update:keyword="(v: string) => { query.keyword = v }"
      @search="onSearch"
      @reset="onReset"
    >
      <n-select
        v-model:value="query.status"
        clearable
        style="width: 150px"
        :options="statusOptions"
        :placeholder="t('common.allStatus')"
        @update:value="onSearch"
      />
      <template #actions>
        <n-button type="primary" @click="onSearch">{{ t('action.search') }}</n-button>
        <n-button secondary @click="onReset">{{ t('action.reset') }}</n-button>
      </template>
    </SearchFilterBar>

    <PaginatedDataTable
      :columns="columns"
      :data="list"
      :loading="loading"
      :total="total"
      v-model:page="page"
      v-model:page-size="pageSize"
      :page-sizes="[10, 20, 50]"
      :empty-text="t('admin.users.empty')"
      :table-props="{ scrollX: 1000 }"
      @update:page="(p: number) => { changePage(p); load() }"
      @update:page-size="(s: number) => { changeSize(s); load() }"
    />

    <!-- 角色设置 -->
    <n-modal
      v-model:show="roleModal"
      preset="card"
      style="width: min(420px, 92vw)"
      :title="t('admin.users.roleTitle', { name: roleTarget?.nickname ?? '' })"
    >
      <n-checkbox-group v-model:value="roleIds">
        <div class="role-options">
          <n-checkbox v-for="opt in roleOptions" :key="opt.value" :value="opt.value" :label="opt.label" />
        </div>
      </n-checkbox-group>
      <template #footer>
        <ModalFooter :loading="roleSaving" :confirm-text="t('action.save')" @cancel="roleModal = false" @confirm="saveRoles" />
      </template>
    </n-modal>

    <!-- 封禁 / 冻结原因 -->
    <n-modal
      v-model:show="reasonVisible"
      preset="dialog"
      type="warning"
      :title="reasonAction === 'ban' ? t('admin.users.ban') : t('admin.users.freeze')"
      :positive-text="t('action.confirm')"
      :negative-text="t('action.cancel')"
      :loading="reasonSubmitting"
      @positive-click="submitReason"
      @negative-click="reasonVisible = false"
    >
      <p>{{ t('admin.users.reasonPrompt', { action: reasonAction === 'ban' ? t('admin.users.ban') : t('admin.users.freeze') }) }}</p>
      <n-input
        v-model:value="reasonText"
        type="textarea"
        maxlength="255"
        show-count
        :placeholder="reasonAction === 'ban' ? t('admin.users.banReason') : t('admin.users.freezeReason')"
      />
    </n-modal>
    </n-card>
  </div>
</template>

<style scoped>
.cell-user {
  display: flex;
  align-items: center;
  gap: 10px;
}
.cell-user__meta .cell-user__email {
  color: var(--app-text-secondary);
  font-size: 12px;
}
.role-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
