<script setup lang="ts">
/**
 * 组织详情 · 成员面板：成员表格（搜索 / 分页 / ⋯ 行操作）+ 添加成员弹窗。
 * 行操作：备注（本人 / org_admin 共用弹窗，空值 = 清除备注）、移出（org_admin）；
 * 授·撤组织管理员不放组织空间页（收敛到管理后台组织详情，docs/contracts/orgs.md）。
 * 移出 / 添加成功后 emit changed，宿主刷新组织概要（成员数等）。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { CirclePlus, MoreFilled } from '@element-plus/icons-vue'
import type { DataTableColumns } from 'naive-ui'
import { NButton, NDropdown, NForm, NFormItem, NIcon, NInput, NModal, NTag } from 'naive-ui'

import { addOrgMembers, listOrgMembers, removeOrgMember, setOrgMemberNote } from '@/api/orgs'
import BaseAvatar from '@/components/BaseAvatar.vue'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { formatCompact } from '@/utils/format'
import { useUserStore } from '@/stores/user'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import type { OrgMemberItem } from '@/types'

const props = defineProps<{
  orgId: string
  isOrgAdmin: boolean
  isMember: boolean
}>()

const emit = defineEmits<{ (e: 'changed'): void }>()

const { t } = useI18n()
const userStore = useUserStore()

const members = ref<OrgMemberItem[]>([])
const membersLoading = ref(false)
const memberKeyword = ref('')
const {
  page: memberPage,
  pageSize: memberPageSize,
  total: memberTotal,
  changePage: changeMemberPage,
  resetPage: resetMemberPage,
} = usePagination()

async function loadMembers() {
  membersLoading.value = true
  try {
    const result = await listOrgMembers(props.orgId, {
      page: memberPage.value,
      page_size: memberPageSize.value,
      keyword: memberKeyword.value || undefined,
    })
    members.value = result.items
    memberTotal.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    membersLoading.value = false
  }
}

function searchMembers() {
  resetMemberPage()
  loadMembers()
}

/** 成员行操作（⋯ 下拉）：备注（本人 / org_admin）、移出（org_admin） */
type MemberAction = 'kick' | 'note'

function memberActions(row: OrgMemberItem): Array<{ key: MemberAction; label: string }> {
  const actions: Array<{ key: MemberAction; label: string }> = []
  if (row.user_id === userStore.user?.id || props.isOrgAdmin) {
    actions.push({ key: 'note', label: t('orgs.members.note') })
  }
  // 移出不提供给自己一行（无退出组织通道，避免误操作后失去自身管理权）
  if (props.isOrgAdmin && row.user_id !== userStore.user?.id) {
    actions.push({ key: 'kick', label: t('orgs.members.kick') })
  }
  return actions
}

function onMemberAction(action: MemberAction, row: OrgMemberItem) {
  if (action === 'note') {
    noteTarget.value = row
    noteValue.value = row.note ?? ''
    noteVisible.value = true
    return
  }
  onKick(row)
}

/** 备注编辑弹窗（本人 / org_admin 共用；空值 = 清除备注） */
const noteVisible = ref(false)
const noteTarget = ref<OrgMemberItem | null>(null)
const noteValue = ref('')
const noteSaving = ref(false)

async function onNoteSave() {
  if (!noteTarget.value) return
  noteSaving.value = true
  try {
    await setOrgMemberNote(props.orgId, noteTarget.value.user_id, noteValue.value.trim() || null)
    message.success(t('orgs.members.noteSuccess'))
    noteVisible.value = false
    await loadMembers()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    noteSaving.value = false
  }
}

function onKick(row: OrgMemberItem) {
  confirmAsyncDialog({
    title: t('orgs.members.kick'),
    content: t('orgs.members.kickConfirm', { name: row.nickname }),
    positiveText: t('orgs.members.kick'),
    action: async () => {
      await removeOrgMember(props.orgId, row.user_id)
    },
    successMessage: t('orgs.members.kickSuccess'),
    onAfterSuccess: () => {
      loadMembers()
      // 成员数等组织概要已变化：宿主重拉组织详情
      emit('changed')
    },
  })
}

// ---- 添加成员（org_admin：单个 UUID + 批量 textarea） ----

const showAddMember = ref(false)
const addingMember = ref(false)
const addForm = ref({ userId: '', batch: '' })

function openAddMember() {
  addForm.value = { userId: '', batch: '' }
  showAddMember.value = true
}

async function doAddMembers() {
  const ids = new Set<string>()
  if (addForm.value.userId.trim()) ids.add(addForm.value.userId.trim())
  for (const line of addForm.value.batch.split(/\r?\n/)) {
    const id = line.trim()
    if (id) ids.add(id)
  }
  if (!ids.size) {
    message.warning(t('orgs.members.userIdPlaceholder'))
    return
  }
  addingMember.value = true
  try {
    await addOrgMembers(props.orgId, [...ids])
    message.success(t('orgs.members.addSuccess'))
    showAddMember.value = false
    await loadMembers()
    // 成员数等组织概要已变化：宿主重拉组织详情
    emit('changed')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    addingMember.value = false
  }
}

const memberColumns = computed<DataTableColumns<OrgMemberItem>>(() => [
  {
    title: t('orgs.members.search'),
    key: 'nickname',
    minWidth: 200,
    ellipsis: { tooltip: true },
    render(row) {
      return h('div', { class: 'cell-user' }, [
        h(BaseAvatar, { src: row.avatar_url, name: row.nickname, size: 32 }),
        h('span', { class: 'cell-strong' }, row.nickname),
        row.user_id === userStore.user?.id
          ? h('span', { class: 'cell-you' }, t('orgs.members.you'))
          : null,
      ])
    },
  },
  {
    title: t('orgs.role.admin'),
    key: 'role',
    width: 130,
    render(row) {
      return h(
        NTag,
        { size: 'small', bordered: false, type: row.is_admin ? 'info' : 'default' },
        {
          default: () => t(row.is_admin ? 'orgs.role.admin' : 'orgs.role.member'),
        },
      )
    },
  },
  {
    title: t('orgs.members.note'),
    key: 'note',
    minWidth: 140,
    ellipsis: { tooltip: true },
    render: (row) => row.note ?? '—',
  },
  {
    title: t('orgs.members.joinedAt'),
    key: 'joined_at',
    width: 170,
    render: (row) => formatCompact(row.joined_at),
  },
  ...(props.isOrgAdmin || props.isMember
    ? [
        {
          title: '',
          key: 'ops',
          width: 48,
          render: (row: OrgMemberItem) =>
            memberActions(row).length
              ? h(
                  NDropdown,
                  {
                    trigger: 'click',
                    options: memberActions(row).map((a) => ({ key: a.key, label: a.label })),
                    onSelect: (key: MemberAction) => onMemberAction(key, row),
                  },
                  {
                    default: () =>
                      h(
                        NButton,
                        {
                          circle: true,
                          quaternary: true,
                          size: 'tiny',
                          'aria-label': t('orgs.detail.more'),
                        },
                        { icon: () => h(NIcon, { component: MoreFilled }) },
                      ),
                  },
                )
              : null,
        },
      ]
    : []),
])

defineExpose({ reload: loadMembers })

onMounted(loadMembers)
</script>

<template>
  <SearchFilterBar
    :keyword="memberKeyword"
    :placeholder="t('orgs.members.search')"
    @update:keyword="
      (v: string) => {
        memberKeyword = v
      }
    "
    @search="searchMembers"
    @reset="searchMembers"
  >
    <template #actions>
      <NButton v-if="isOrgAdmin" size="small" type="primary" secondary @click="openAddMember">
        <template #icon>
          <NIcon :component="CirclePlus" />
        </template>
        {{ t('orgs.members.add') }}
      </NButton>
      <RefreshButton
        :loading="membersLoading"
        :aria-label="t('action.refresh')"
        @click="loadMembers"
      />
    </template>
  </SearchFilterBar>
  <PaginatedDataTable
    :columns="memberColumns"
    :data="members"
    :loading="membersLoading"
    :total="memberTotal"
    :page="memberPage"
    :page-size="memberPageSize"
    :empty-text="t('orgs.members.empty')"
    :table-props="{ size: 'small' }"
    @update:page="
      (p: number) => {
        changeMemberPage(p)
        loadMembers()
      }
    "
  />

  <!-- 成员备注弹窗：本人 / org_admin 共用；空值 = 清除备注 -->
  <NModal
    v-model:show="noteVisible"
    preset="card"
    style="width: 400px"
    :title="t('orgs.members.noteTarget', { name: noteTarget?.nickname ?? '' })"
  >
    <NInput
      v-model:value="noteValue"
      :placeholder="t('orgs.members.notePlaceholder')"
      :maxlength="64"
      show-count
      clearable
      @keyup.enter="onNoteSave"
    />
    <template #footer>
      <div class="modal-actions">
        <NButton size="small" quaternary @click="noteVisible = false">
          {{ t('action.cancel') }}
        </NButton>
        <NButton size="small" type="primary" :loading="noteSaving" @click="onNoteSave">
          {{ t('action.save') }}
        </NButton>
      </div>
    </template>
  </NModal>

  <!-- 添加成员弹窗（org_admin）：单个 UUID + 批量 textarea，已在册由后端跳过 -->
  <NModal
    v-model:show="showAddMember"
    preset="card"
    style="width: 480px"
    :title="t('orgs.members.addTitle')"
  >
    <NForm label-placement="top">
      <NFormItem :label="t('orgs.members.userId')">
        <NInput v-model:value="addForm.userId" :placeholder="t('orgs.members.userIdPlaceholder')" />
      </NFormItem>
      <NFormItem :label="t('orgs.members.batchIds')">
        <NInput
          v-model:value="addForm.batch"
          type="textarea"
          :rows="4"
          :placeholder="t('orgs.members.batchPlaceholder')"
        />
      </NFormItem>
    </NForm>
    <template #footer>
      <div class="modal-actions">
        <NButton size="small" quaternary @click="showAddMember = false">
          {{ t('action.cancel') }}
        </NButton>
        <NButton size="small" type="primary" :loading="addingMember" @click="doAddMembers">
          {{ t('action.confirm') }}
        </NButton>
      </div>
    </template>
  </NModal>
</template>

<style scoped>
/* 表格单元格：头像 + 文本行内组合 */
.cell-user {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.cell-strong {
  font-weight: 600;
}
.cell-you {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 650;
  line-height: 1;
  padding: 2px 6px;
  border-radius: 999px;
  color: var(--app-primary);
  background: color-mix(in srgb, var(--app-primary) 12%, transparent);
}

/* 弹窗底部动作区 */
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
