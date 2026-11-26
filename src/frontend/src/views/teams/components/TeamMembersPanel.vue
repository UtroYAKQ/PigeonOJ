<script setup lang="ts">
/**
 * 团队详情 · 成员面板：成员卡片列表（搜索 / 分页 / ⋯ 行操作）。
 * 行操作：备注（本人 / 管理员共用弹窗，空值 = 清除备注）、设·撤管理员（仅创建者）、
 * 移出（管理员）；移出成功后 emit changed，宿主刷新团队概要（成员数等）。
 */
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { MoreFilled } from '@element-plus/icons-vue'
import { NButton, NDropdown, NIcon, NInput, NModal, NSpin } from 'naive-ui'

import { kickTeamMember, listTeamMembers, setTeamAdmin, setTeamMemberNote } from '@/api/teams'
import BaseAvatar from '@/components/BaseAvatar.vue'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { formatCompact } from '@/utils/format'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import { useUserStore } from '@/stores/user'
import type { TeamMemberItem } from '@/types'

const props = defineProps<{
  teamId: string
  isCreator: boolean
  isAdmin: boolean
}>()

const emit = defineEmits<{ (e: 'changed'): void }>()

const { t } = useI18n()
const userStore = useUserStore()

const members = ref<TeamMemberItem[]>([])
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
    const result = await listTeamMembers(props.teamId, {
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

function memberRoleOf(row: TeamMemberItem): 'creator' | 'admin' | 'member' {
  if (row.is_creator) return 'creator'
  if (row.is_admin) return 'admin'
  return 'member'
}

/** 成员行操作（⋯ 下拉）：设 / 撤管理员（仅创建者）、移出（管理员）、备注（本人 / 管理员） */
type MemberAction = 'grant' | 'revoke' | 'kick' | 'note'

function memberActions(row: TeamMemberItem): Array<{ key: MemberAction; label: string }> {
  const actions: Array<{ key: MemberAction; label: string }> = []
  // 备注：本人可备注自己（普通成员唯一可见的行操作），团队创建者 / 管理员可备注任意成员
  if (row.user_id === userStore.user?.id || props.isAdmin) {
    actions.push({ key: 'note', label: t('teams.members.note') })
  }
  if (props.isCreator && !row.is_creator) {
    actions.push({
      key: row.is_admin ? 'revoke' : 'grant',
      label: t(row.is_admin ? 'teams.members.revokeAdmin' : 'teams.members.grantAdmin'),
    })
  }
  // 移出不提供给自己一行：退出走「退出团队」入口（exited 语义，非 kicked）
  if (props.isAdmin && !row.is_creator && row.user_id !== userStore.user?.id) {
    actions.push({ key: 'kick', label: t('teams.members.kick') })
  }
  return actions
}

function onMemberAction(action: MemberAction, row: TeamMemberItem) {
  if (action === 'grant' || action === 'revoke') {
    void onSetAdmin(row, action === 'grant')
    return
  }
  if (action === 'note') {
    noteTarget.value = row
    noteValue.value = row.note ?? ''
    noteVisible.value = true
    return
  }
  onKick(row)
}

/** 备注编辑弹窗（本人 / 管理员共用；空值 = 清除备注） */
const noteVisible = ref(false)
const noteTarget = ref<TeamMemberItem | null>(null)
const noteValue = ref('')
const noteSaving = ref(false)

async function onNoteSave() {
  if (!noteTarget.value) return
  noteSaving.value = true
  try {
    await setTeamMemberNote(props.teamId, noteTarget.value.user_id, noteValue.value.trim() || null)
    message.success(t('teams.members.noteSuccess'))
    noteVisible.value = false
    await loadMembers()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    noteSaving.value = false
  }
}

async function onSetAdmin(row: TeamMemberItem, grant: boolean) {
  try {
    await setTeamAdmin(props.teamId, row.user_id, grant)
    message.success(t(grant ? 'teams.members.grantSuccess' : 'teams.members.revokeSuccess'))
    await loadMembers()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

function onKick(row: TeamMemberItem) {
  confirmAsyncDialog({
    title: t('teams.members.kick'),
    content: t('teams.members.kickConfirm', { name: row.nickname }),
    positiveText: t('teams.members.kick'),
    action: async () => {
      await kickTeamMember(props.teamId, row.user_id)
    },
    successMessage: t('teams.members.kickSuccess'),
    onAfterSuccess: () => {
      loadMembers()
      // 成员数等团队概要已变化：宿主重拉团队详情
      emit('changed')
    },
  })
}

defineExpose({ reload: loadMembers })

onMounted(loadMembers)
</script>

<template>
  <SearchFilterBar
    :keyword="memberKeyword"
    :placeholder="t('teams.members.search')"
    @update:keyword="
      (v: string) => {
        memberKeyword = v
      }
    "
    @search="searchMembers"
    @reset="searchMembers"
  >
    <template #actions>
      <RefreshButton
        :loading="membersLoading"
        :aria-label="t('action.refresh')"
        @click="loadMembers"
      />
    </template>
  </SearchFilterBar>
  <PaginatedDataTable
    :data="members"
    :loading="membersLoading"
    :total="memberTotal"
    :page="memberPage"
    :page-size="memberPageSize"
    :empty-text="t('teams.members.empty')"
    @update:page="
      (p: number) => {
        changeMemberPage(p)
        loadMembers()
      }
    "
  >
    <template #content>
      <div class="pane-scroll">
        <NSpin :show="membersLoading" class="pane-spin">
          <ul v-if="members.length" class="tile-grid">
            <li v-for="member in members" :key="member.user_id" class="tile">
              <BaseAvatar :src="member.avatar_url" :name="member.nickname" :size="40" />
              <div class="tile__body">
                <div class="tile__head">
                  <span class="tile__title" :title="member.nickname">{{ member.nickname }}</span>
                  <span
                    v-if="member.note"
                    class="tile__note"
                    :title="t('teams.members.note') + '：' + member.note"
                  >
                    {{ member.note }}
                  </span>
                  <span v-if="member.user_id === userStore.user?.id" class="tile__you">
                    {{ t('teams.members.you') }}
                  </span>
                  <NDropdown
                    v-if="memberActions(member).length"
                    class="tile__ops"
                    trigger="click"
                    :options="memberActions(member)"
                    @select="(action: MemberAction) => onMemberAction(action, member)"
                  >
                    <NButton circle quaternary size="tiny" :aria-label="t('teams.detail.more')">
                      <template #icon>
                        <NIcon :component="MoreFilled" />
                      </template>
                    </NButton>
                  </NDropdown>
                </div>
                <div class="tile__foot">
                  <span class="dot-chip" :class="`dot-chip--${memberRoleOf(member)}`">
                    <span class="dot-chip__dot" aria-hidden="true" />
                    {{ t(`teams.role.${memberRoleOf(member)}`) }}
                  </span>
                  <span class="tile__meta">
                    {{ t('teams.members.joinedAt') }}
                    {{ formatCompact(member.joined_at) }}
                  </span>
                </div>
              </div>
            </li>
          </ul>
        </NSpin>
      </div>
    </template>
  </PaginatedDataTable>

  <!-- 成员备注弹窗：本人 / 管理员共用；空值 = 清除备注 -->
  <NModal
    v-model:show="noteVisible"
    preset="card"
    style="width: 400px"
    :title="t('teams.members.noteTarget', { name: noteTarget?.nickname ?? '' })"
  >
    <NInput
      v-model:value="noteValue"
      :placeholder="t('teams.members.notePlaceholder')"
      :maxlength="64"
      show-count
      clearable
      @keyup.enter="onNoteSave"
    />
    <template #footer>
      <div class="note-modal__actions">
        <NButton size="small" quaternary @click="noteVisible = false">
          {{ t('action.cancel') }}
        </NButton>
        <NButton size="small" type="primary" :loading="noteSaving" @click="onNoteSave">
          {{ t('action.save') }}
        </NButton>
      </div>
    </template>
  </NModal>
</template>

<style scoped>
/* pane 内滚动区：列表撑满，超出滚动 */
.pane-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: grid;
}
.pane-spin {
  min-height: 100%;
  display: flex;
  flex-direction: column;
}
.pane-spin :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* 成员卡片：紧凑小卡片 */
.tile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
  list-style: none;
  margin: 0;
  padding: 0 0 4px;
  align-content: start;
}
.tile {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
  padding: 14px 16px;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  background: var(--app-card-bg, #fff);
  transition: border-color 0.15s ease;
}
.tile:hover {
  border-color: var(--app-text-muted);
}
.tile__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tile__head {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.tile__title {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-size: 14px;
  font-weight: 650;
  line-height: 1.35;
  color: var(--app-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.15s ease;
}
.tile__you {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 650;
  line-height: 1;
  padding: 2px 6px;
  border-radius: 999px;
  color: var(--app-primary);
  background: color-mix(in srgb, var(--app-primary) 12%, transparent);
}
/* 成员备注：与昵称区分子字体与颜色（小号 / 次要色 / 中性底 chip），截断防挤压 */
.tile__note {
  flex-shrink: 0;
  max-width: 40%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  font-weight: 400;
  line-height: 1.4;
  padding: 1px 6px;
  border-radius: 3px;
  color: var(--app-text-secondary);
  background: var(--app-muted-bg);
}
.note-modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.tile__ops {
  flex-shrink: 0;
  margin: -2px -4px -2px 0;
}
.tile__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}
.tile__meta {
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.35;
  font-variant-numeric: tabular-nums;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dot-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
  font-size: 11px;
  line-height: 1;
  color: var(--app-text-secondary);
}
.dot-chip__dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--app-text-muted);
}
.dot-chip--creator {
  color: var(--app-warning);
}
.dot-chip--creator .dot-chip__dot {
  background: var(--app-warning);
}
.dot-chip--admin {
  color: var(--app-info);
}
.dot-chip--admin .dot-chip__dot {
  background: var(--app-info);
}
@media (hover: hover) {
  .tile__ops {
    opacity: 0;
    transition: opacity 0.15s ease;
  }
  .tile:hover .tile__ops,
  .tile:focus-within .tile__ops {
    opacity: 1;
  }
}

/* 响应式 */
@media (max-width: 860px) {
  .tile-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
