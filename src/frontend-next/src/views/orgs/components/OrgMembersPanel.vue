<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, Plus } from '@lucide/vue'

import { adminListOrgMembers } from '@/api/admin'
import {
  addOrgMembers,
  listOrgMembers,
  lookupOrgMemberCandidates,
  removeOrgMember,
  setOrgMemberAdmin,
  setOrgMemberNote,
} from '@/api/orgs'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import UserEmailPicker from '@/components/common/UserEmailPicker.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import RowActions from '@/components/teams/RowActions.vue'
import type { RowAction } from '@/components/teams/types'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'

import { usePagination } from '@/composables/usePagination'
import { useUserStore } from '@/stores/user'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { OrgMemberItem, UserCandidate } from '@/types'

const props = defineProps<{ orgId: string; canManage: boolean; adminMode?: boolean }>()

const { t } = useI18n()
const userStore = useUserStore()

const members = ref<OrgMemberItem[]>([])
const loading = ref(false)
const keyword = ref('')
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const query = {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    }
    const result = props.adminMode
      ? await adminListOrgMembers(props.orgId, query)
      : await listOrgMembers(props.orgId, query)
    if (!isCurrent(seq)) return
    members.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('orgs.detail.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

function onSearch(): void {
  resetPage()
  void load()
}

function onPageChange(value: number): void {
  changePage(value)
  void load()
}

// ---------------- 添加成员 ----------------

const addOpen = ref(false)
const selectedUsers = ref<UserCandidate[]>([])
const adding = ref(false)

function openAdd(): void {
  selectedUsers.value = []
  addOpen.value = true
}

async function searchUsers(email: string): Promise<UserCandidate[]> {
  const rows = await lookupOrgMemberCandidates(props.orgId, email)
  return rows.map((row) => ({
    id: row.id,
    email: row.email,
    nickname: row.nickname,
    avatar_url: row.avatar_url,
    disabled: row.is_member,
    note: row.is_member ? t('orgs.members.alreadyMember') : undefined,
  }))
}

async function submitAdd(): Promise<void> {
  const ids = selectedUsers.value.map((item) => item.id)
  if (!ids.length) {
    message.warning(t('orgs.members.selectRequired'))
    return
  }
  adding.value = true
  try {
    await addOrgMembers(props.orgId, ids)
    message.success(t('orgs.members.addSuccess'))
    addOpen.value = false
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    adding.value = false
  }
}

// ---------------- 备注 ----------------

const noteOpen = ref(false)
const noteTarget = ref<OrgMemberItem | null>(null)
const noteValue = ref('')
const savingNote = ref(false)

function openNote(member: OrgMemberItem): void {
  noteTarget.value = member
  noteValue.value = member.note ?? ''
  noteOpen.value = true
}

async function submitNote(): Promise<void> {
  const target = noteTarget.value
  if (!target) return
  savingNote.value = true
  try {
    await setOrgMemberNote(props.orgId, target.user_id, noteValue.value.trim() || null)
    message.success(t('orgs.members.noteSuccess'))
    noteOpen.value = false
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    savingNote.value = false
  }
}

// ---------------- 行操作 ----------------

function actionsFor(row: OrgMemberItem): RowAction[] {
  if (!props.canManage) return []
  const isSelf = row.user_id === userStore.user?.id
  const actions: RowAction[] = []
  if (isSelf || props.canManage) {
    actions.push({ key: 'note', label: t('orgs.members.note') })
  }
  if (!isSelf) {
    actions.push({
      key: 'toggleAdmin',
      label: row.is_admin ? t('orgs.members.revokeAdmin') : t('orgs.members.grantAdmin'),
    })
    actions.push({ key: 'remove', label: t('orgs.members.kick'), destructive: true })
  }
  return actions
}

function onAction(key: string, row: OrgMemberItem): void {
  if (key === 'note') {
    openNote(row)
    return
  }
  if (key === 'toggleAdmin') {
    confirmAsyncDialog({
      title: row.is_admin ? t('orgs.members.revokeAdmin') : t('orgs.members.grantAdmin'),
      content: row.nickname,
      action: () => setOrgMemberAdmin(props.orgId, row.user_id, !row.is_admin),
      successMessage: row.is_admin
        ? t('orgs.members.revokeSuccess')
        : t('orgs.members.grantSuccess'),
      onAfterSuccess: () => load(),
    })
    return
  }
  if (key === 'remove') {
    confirmAsyncDialog({
      title: t('orgs.members.kick'),
      content: t('orgs.members.kickConfirm', { name: row.nickname }),
      positiveText: t('orgs.members.kick'),
      danger: true,
      action: () => removeOrgMember(props.orgId, row.user_id),
      successMessage: t('orgs.members.kickSuccess'),
      onAfterSuccess: () => load(),
    })
  }
}

const columns = computed<AppTableColumn<OrgMemberItem>[]>(() => {
  const cols: AppTableColumn<OrgMemberItem>[] = [
    {
      key: 'nickname',
      title: t('teams.members.user'),
      cell: (row) =>
        h('div', { class: 'flex min-w-0 items-center gap-2.5 py-0.5' }, [
          h(BaseAvatar, { src: row.avatar_url, name: row.nickname, size: 30 }),
          h('span', { class: 'truncate text-[13px] font-medium', title: row.nickname }, row.nickname),
          row.user_id === userStore.user?.id
            ? h(
                'span',
                {
                  class:
                    'shrink-0 rounded border border-border bg-muted px-1.5 text-[10px] text-muted-foreground',
                },
                t('orgs.members.you'),
              )
            : null,
        ]),
    },
    {
      key: 'role',
      title: t('teams.members.role'),
      width: '120px',
      cell: (row) =>
        h(ToneBadge, {
          tone: row.is_admin ? 'warning' : 'default',
          dot: true,
          label: row.is_admin ? t('orgs.role.admin') : t('orgs.role.member'),
        }),
    },
    {
      key: 'joined_at',
      title: t('orgs.members.joinedAt'),
      width: '160px',
      cell: (row) => formatDateTime(row.joined_at),
      cellClass: 'text-[12.5px] text-muted-foreground',
    },
    {
      key: 'note',
      title: t('orgs.members.note'),
      cell: (row) => row.note ?? '—',
      cellClass: 'text-[12.5px] text-muted-foreground',
    },
  ]
  if (props.canManage) {
    cols.push({
      key: 'ops',
      width: '56px',
      align: 'right',
      cell: (row) =>
        h(RowActions, {
          actions: actionsFor(row),
          label: t('teams.detail.more'),
          onSelect: (key: string) => onAction(key, row),
        }),
    })
  }
  return cols
})

onMounted(load)
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3">
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('orgs.members.search')"
      @update:keyword="keyword = $event"
      @search="onSearch"
      @reset="onSearch"
    >
      <template #actions>
        <Button v-if="canManage" variant="outline" size="toolbar" @click="openAdd">
          <Plus class="size-4" />
          {{ t('orgs.members.add') }}
        </Button>
        <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <PaginatedTable
      :columns="columns"
      :data="members"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      show-size-picker
      :empty-text="t('orgs.members.empty')"
      @update:page="onPageChange"
    />

    <Dialog v-model:open="addOpen">
      <DialogContent class="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>{{ t('orgs.members.addTitle') }}</DialogTitle>
          <DialogDescription>{{ t('orgs.members.addHint') }}</DialogDescription>
        </DialogHeader>
        <UserEmailPicker
          v-model="selectedUsers"
          :search="searchUsers"
          :placeholder="t('orgs.members.emailPlaceholder')"
        />
        <DialogFooter>
          <Button variant="outline" size="sm" :disabled="adding" @click="addOpen = false">
            {{ t('action.cancel') }}
          </Button>
          <Button size="sm" :disabled="adding" @click="submitAdd">
            <Loader2 v-if="adding" class="size-4 animate-spin" />
            {{ t('orgs.members.add') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="noteOpen">
      <DialogContent class="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>
            {{ t('orgs.members.noteTarget', { name: noteTarget?.nickname ?? '' }) }}
          </DialogTitle>
          <DialogDescription class="sr-only">{{ t('orgs.members.note') }}</DialogDescription>
        </DialogHeader>
        <Input v-model="noteValue" maxlength="64" :placeholder="t('orgs.members.notePlaceholder')" />
        <DialogFooter>
          <Button variant="outline" size="sm" :disabled="savingNote" @click="noteOpen = false">
            {{ t('action.cancel') }}
          </Button>
          <Button size="sm" :disabled="savingNote" @click="submitNote">
            <Loader2 v-if="savingNote" class="size-4 animate-spin" />
            {{ t('action.save') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>