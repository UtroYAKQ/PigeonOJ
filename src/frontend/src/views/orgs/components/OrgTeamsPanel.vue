<script setup lang="ts">
/**
 * 组织详情 · 组织团队面板：团队表格（搜索 / 分页 / 行点击进团队详情）。
 * 创建团队（org_admin）：teams.org_id 固定为本组织，创建者自动 team_creator。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { CirclePlus } from '@element-plus/icons-vue'
import type { DataTableColumns } from 'naive-ui'
import { NButton, NForm, NFormItem, NIcon, NInput, NModal, NTag } from 'naive-ui'

import { createOrgTeam, listOrgTeams } from '@/api/orgs'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { formatDateTime } from '@/utils/format'
import BaseAvatar from '@/components/BaseAvatar.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import type { TeamSummary } from '@/types'

const props = defineProps<{
  orgId: string
  isOrgAdmin: boolean
}>()

const { t } = useI18n()
const router = useRouter()

const teams = ref<TeamSummary[]>([])
const teamsLoading = ref(false)
const teamKeyword = ref('')
const {
  page: teamPage,
  pageSize: teamPageSize,
  total: teamTotal,
  changePage: changeTeamPage,
  resetPage: resetTeamPage,
} = usePagination()

async function loadTeams() {
  teamsLoading.value = true
  try {
    const result = await listOrgTeams(props.orgId, {
      page: teamPage.value,
      page_size: teamPageSize.value,
      keyword: teamKeyword.value || undefined,
    })
    teams.value = result.items
    teamTotal.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    teamsLoading.value = false
  }
}

function searchTeams() {
  resetTeamPage()
  loadTeams()
}

const teamColumns = computed<DataTableColumns<TeamSummary>>(() => [
  {
    title: t('teams.list.name'),
    key: 'name',
    minWidth: 200,
    ellipsis: { tooltip: true },
    render(row) {
      return h('div', { class: 'cell-user' }, [
        h(BaseAvatar, { src: row.avatar_url, name: row.name, size: 32, kind: 'team' }),
        h('span', { class: 'cell-strong' }, row.name),
      ])
    },
  },
  {
    title: t('teams.list.description'),
    key: 'description',
    minWidth: 180,
    ellipsis: { tooltip: true },
    render: (row) => row.description ?? '—',
  },
  {
    title: t('teams.settings.visibility'),
    key: 'visibility',
    width: 90,
    render: (row) =>
      h(
        NTag,
        {
          size: 'small',
          bordered: false,
          type: row.visibility === 'public' ? 'success' : 'default',
        },
        {
          default: () =>
            t(
              row.visibility === 'public'
                ? 'teams.settings.visibilityPublic'
                : 'teams.settings.visibilityPrivate',
            ),
        },
      ),
  },
  {
    title: t('orgs.teams.memberCount'),
    key: 'member_count',
    width: 80,
    align: 'center',
    render: (row) => String(row.member_count),
  },
  {
    title: t('teams.list.createdAt'),
    key: 'created_at',
    width: 170,
    render: (row) => formatDateTime(row.created_at),
  },
])

function rowPropsOfTeam(row: TeamSummary) {
  return { style: 'cursor: pointer;', onClick: () => router.push(`/teams/${row.id}`) }
}

/** 创建团队（org_admin；teams.org_id 固定为本组织，创建者自动 team_creator） */
const showCreateTeam = ref(false)
const creatingTeam = ref(false)
const teamForm = ref({ name: '', description: '', visibility: 'private' as 'public' | 'private' })

function openCreateTeam() {
  teamForm.value = { name: '', description: '', visibility: 'private' }
  showCreateTeam.value = true
}

async function doCreateTeam() {
  if (!teamForm.value.name.trim()) {
    message.warning(t('teams.create.nameRequired'))
    return
  }
  creatingTeam.value = true
  try {
    await createOrgTeam(props.orgId, {
      name: teamForm.value.name.trim(),
      description: teamForm.value.description.trim() || undefined,
      visibility: teamForm.value.visibility,
    })
    message.success(t('orgs.teams.created'))
    showCreateTeam.value = false
    await loadTeams()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    creatingTeam.value = false
  }
}

onMounted(loadTeams)
</script>

<template>
  <SearchFilterBar
    :keyword="teamKeyword"
    :placeholder="t('orgs.teams.search')"
    @update:keyword="
      (v: string) => {
        teamKeyword = v
      }
    "
    @search="searchTeams"
    @reset="searchTeams"
  >
    <template #actions>
      <NButton v-if="isOrgAdmin" size="small" type="primary" @click="openCreateTeam">
        <template #icon>
          <NIcon :component="CirclePlus" />
        </template>
        {{ t('orgs.teams.create') }}
      </NButton>
      <RefreshButton :loading="teamsLoading" :aria-label="t('action.refresh')" @click="loadTeams" />
    </template>
  </SearchFilterBar>
  <PaginatedDataTable
    :columns="teamColumns"
    :data="teams"
    :loading="teamsLoading"
    :total="teamTotal"
    :page="teamPage"
    :page-size="teamPageSize"
    :empty-text="t('orgs.teams.empty')"
    :table-props="{
      size: 'small',
      rowKey: (row: TeamSummary) => row.id,
      rowProps: rowPropsOfTeam,
    }"
    @update:page="
      (p: number) => {
        changeTeamPage(p)
        loadTeams()
      }
    "
  />

  <!-- 创建团队弹窗（org_admin）：teams.org_id 固定为本组织 -->
  <NModal
    v-model:show="showCreateTeam"
    preset="card"
    style="width: 480px"
    :title="t('orgs.teams.createTitle')"
  >
    <NForm label-placement="top">
      <NFormItem :label="t('teams.create.name')" required>
        <NInput
          v-model:value="teamForm.name"
          maxlength="64"
          :placeholder="t('teams.create.namePlaceholder')"
        />
      </NFormItem>
      <NFormItem :label="t('teams.create.description')">
        <NInput
          v-model:value="teamForm.description"
          type="textarea"
          :rows="3"
          maxlength="2000"
          :placeholder="t('teams.create.descriptionPlaceholder')"
        />
      </NFormItem>
      <NFormItem :label="t('teams.settings.visibility')">
        <n-radio-group v-model:value="teamForm.visibility">
          <n-radio value="private">{{ t('teams.settings.visibilityPrivate') }}</n-radio>
          <n-radio value="public">{{ t('teams.settings.visibilityPublic') }}</n-radio>
        </n-radio-group>
      </NFormItem>
    </NForm>
    <template #footer>
      <div class="modal-actions">
        <NButton size="small" quaternary @click="showCreateTeam = false">
          {{ t('action.cancel') }}
        </NButton>
        <NButton size="small" type="primary" :loading="creatingTeam" @click="doCreateTeam">
          {{ t('action.save') }}
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

/* 弹窗底部动作区 */
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
