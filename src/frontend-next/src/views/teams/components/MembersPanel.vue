<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { kickTeamMember, listTeamMembers, setTeamAdmin, setTeamMemberNote } from '@/api/teams'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import RowActions from '@/components/teams/RowActions.vue'
import TeamMemberRow from '@/components/teams/TeamMemberRow.vue'
import TeamRoleBadge from '@/components/teams/TeamRoleBadge.vue'
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
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { TeamMemberItem } from '@/types'

type MemberAction = 'grant' | 'revoke' | 'kick' | 'note'

const props = defineProps<{
  teamId: string
  isCreator: boolean
  isAdmin: boolean
  currentUserId: string
  refreshSignal?: number
}>()

const emit = defineEmits<{ changed: [] }>()

const { t } = useI18n()

const members = ref<TeamMemberItem[]>([])
const loading = ref(false)
const keyword = ref('')
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listTeamMembers(props.teamId, {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    })
    if (!isCurrent(seq)) return
    members.value = result.items
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

function onPageChange(value: number): void {
  changePage(value)
  void load()
}

function memberRoleOf(row: TeamMemberItem): 'creator' | 'admin' | 'member' {
  if (row.is_creator) return 'creator'
  if (row.is_admin) return 'admin'
  return 'member'
}

function memberActions(row: TeamMemberItem): RowAction[] {
  const actions: RowAction[] = []
  // 备注：本人可备注自己；团队创建者 / 管理员可备注任意成员
  if (row.user_id === props.currentUserId || props.isAdmin) {
    actions.push({ key: 'note', label: t('teams.members.note') })
  }
  if (props.isCreator && !row.is_creator) {
    actions.push({
      key: row.is_admin ? 'revoke' : 'grant',
      label: t(row.is_admin ? 'teams.members.revokeAdmin' : 'teams.members.grantAdmin'),
    })
  }
  // 移出不提供给自己一行：退出走「团队设置 - 退出团队」（exited 语义，非 kicked）
  if (props.isAdmin && !row.is_creator && row.user_id !== props.currentUserId) {
    actions.push({ key: 'kick', label: t('teams.members.kick'), destructive: true })
  }
  return actions
}

function onMemberAction(action: MemberAction, row: TeamMemberItem): void {
  if (action === 'grant' || action === 'revoke') {
    void setAdmin(row, action === 'grant')
    return
  }
  if (action === 'note') {
    noteTarget.value = row
    noteValue.value = row.note ?? ''
    noteOpen.value = true
    return
  }
  kick(row)
}

async function setAdmin(row: TeamMemberItem, grant: boolean): Promise<void> {
  try {
    await setTeamAdmin(props.teamId, row.user_id, grant)
    message.success(t(grant ? 'teams.members.grantSuccess' : 'teams.members.revokeSuccess'))
    await load()
    emit('changed')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

function kick(row: TeamMemberItem): void {
  confirmAsyncDialog({
    title: t('teams.members.kick'),
    content: t('teams.members.kickConfirm', { name: row.nickname }),
    positiveText: t('teams.members.kick'),
    danger: true,
    action: () => kickTeamMember(props.teamId, row.user_id),
    successMessage: t('teams.members.kickSuccess'),
    onAfterSuccess: async () => {
      await load()
      emit('changed')
    },
  })
}

// ---- 成员备注弹窗（本人 / 管理员共用；空值 = 清除备注） ----
const noteOpen = ref(false)
const noteTarget = ref<TeamMemberItem | null>(null)
const noteValue = ref('')
const noteSaving = ref(false)

async function saveNote(): Promise<void> {
  if (!noteTarget.value || noteSaving.value) return
  noteSaving.value = true
  try {
    await setTeamMemberNote(props.teamId, noteTarget.value.user_id, noteValue.value.trim() || null)
    message.success(t('teams.members.noteSuccess'))
    noteOpen.value = false
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    noteSaving.value = false
  }
}

const columns = computed<AppTableColumn<TeamMemberItem>[]>(() => [
  {
    key: 'member',
    title: t('teams.members.user'),
    cell: (row) => h(TeamMemberRow, { member: row, isSelf: row.user_id === props.currentUserId }),
  },
  {
    key: 'role',
    title: t('teams.members.role'),
    width: '120px',
    cell: (row) => h(TeamRoleBadge, { role: memberRoleOf(row) }),
  },
  {
    key: 'joined_at',
    title: t('teams.members.joinedAt'),
    width: '170px',
    cell: (row) => formatDateTime(row.joined_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'ops',
    width: '56px',
    align: 'right',
    cell: (row) => {
      const actions = memberActions(row)
      if (!actions.length) return null
      return h(RowActions, {
        actions,
        label: t('teams.detail.more'),
        onSelect: (key: string) => onMemberAction(key as MemberAction, row),
      })
    },
  },
])

onMounted(load)

watch(
  () => props.refreshSignal,
  (value, previous) => {
    if (value !== previous) void load()
  },
)
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3">
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('teams.members.search')"
      @update:keyword="keyword = $event"
      @search="onSearch"
      @reset="onSearch"
    >
      <template #actions>
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
      :empty-text="t('teams.members.empty')"
      @update:page="onPageChange"
    >
      <template #pager-left>
        <span class="tabular-nums">{{ t('teams.pane.memberTotal', { count: total }) }}</span>
      </template>
    </PaginatedTable>

    <Dialog v-model:open="noteOpen">
      <DialogContent class="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>
            {{ t('teams.members.noteTarget', { name: noteTarget?.nickname ?? '' }) }}
          </DialogTitle>
          <DialogDescription class="sr-only">
            {{ t('teams.members.notePlaceholder') }}
          </DialogDescription>
        </DialogHeader>
        <Input
          v-model="noteValue"
          :maxlength="64"
          :placeholder="t('teams.members.notePlaceholder')"
          class="h-9 text-[13px]"
          @keyup.enter="saveNote"
        />
        <DialogFooter>
          <Button variant="outline" size="sm" :disabled="noteSaving" @click="noteOpen = false">
            {{ t('action.cancel') }}
          </Button>
          <Button size="sm" :disabled="noteSaving" @click="saveNote">
            <Loader2 v-if="noteSaving" class="size-3.5 animate-spin" />
            {{ t('action.save') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
