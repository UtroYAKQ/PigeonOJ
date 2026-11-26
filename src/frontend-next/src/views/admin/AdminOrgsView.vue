<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2, Plus } from '@lucide/vue'

import { adminListOrgs } from '@/api/admin'
import { createOrg, disbandOrg } from '@/api/orgs'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
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
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { usePagination } from '@/composables/usePagination'
import { confirmDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { OrgDetail } from '@/types'

const router = useRouter()
const { t } = useI18n()

const orgs = ref<OrgDetail[]>([])
const loading = ref(false)
const keyword = ref('')
const status = ref<'all' | 'active' | 'disbanded'>('all')
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await adminListOrgs({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      status: status.value === 'all' ? undefined : status.value,
    })
    if (!isCurrent(seq)) return
    orgs.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('admin.orgs.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

function onSearch(): void {
  resetPage()
  void load()
}

// ---------------- 创建组织 ----------------

const createOpen = ref(false)
const creating = ref(false)
const form = reactive({ name: '', description: '', adminIds: '' })

function openCreate(): void {
  form.name = ''
  form.description = ''
  form.adminIds = ''
  createOpen.value = true
}

async function submitCreate(): Promise<void> {
  if (!form.name.trim()) {
    message.warning(t('orgs.create.nameRequired'))
    return
  }
  creating.value = true
  try {
    const adminIds = [...new Set(form.adminIds.split(/\s+/).filter(Boolean))]
    const org = await createOrg({
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      admin_user_ids: adminIds.length ? adminIds : undefined,
    })
    message.success(t('admin.orgs.createSuccess'))
    createOpen.value = false
    await load()
    void router.push(`/admin/orgs/${org.id}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    creating.value = false
  }
}

async function onDisband(row: OrgDetail): Promise<void> {
  const ok = await confirmDialog({
    title: t('orgs.settings.disband'),
    content: t('orgs.settings.disbandConfirm'),
    positiveText: t('orgs.settings.disband'),
    negativeText: t('action.cancel'),
    danger: true,
  })
  if (!ok) return
  try {
    await disbandOrg(row.id)
    message.success(t('orgs.settings.disbandSuccess'))
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

function actionsFor(row: OrgDetail): RowAction[] {
  return row.status === 'active'
    ? [{ key: 'disband', label: t('orgs.settings.disband'), destructive: true }]
    : []
}

const columns = computed<AppTableColumn<OrgDetail>[]>(() => [
  {
    key: 'name',
    title: t('admin.orgs.org'),
    cell: (row) =>
      h('div', { class: 'flex min-w-0 items-center gap-2.5 py-0.5' }, [
        h(BaseAvatar, { src: row.avatar_url, name: row.name, size: 34, kind: 'team', round: false, radius: 8 }),
        h('span', { class: 'truncate font-medium', title: row.name }, row.name),
      ]),
  },
  {
    key: 'member_count',
    title: t('admin.orgs.memberCount'),
    width: '100px',
    align: 'right',
    cell: (row) => String(row.member_count),
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'team_count',
    title: t('admin.orgs.teamCount'),
    width: '100px',
    align: 'right',
    cell: (row) => String(row.team_count),
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'status',
    title: t('admin.orgs.status'),
    width: '100px',
    cell: (row) =>
      h(ToneBadge, {
        tone: row.status === 'active' ? 'success' : 'default',
        label:
          row.status === 'active' ? t('admin.orgs.statusActive') : t('admin.orgs.statusDisbanded'),
      }),
  },
  {
    key: 'created_at',
    title: t('admin.orgs.createdAt'),
    width: '160px',
    cell: (row) => formatDateTime(row.created_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'ops',
    width: '56px',
    align: 'right',
    cellClass: 'overflow-visible text-clip px-1',
    cell: (row) =>
      h(RowActions, {
        actions: actionsFor(row),
        label: t('action.more'),
        onSelect: () => onDisband(row),
      }),
  },
])

onMounted(load)
</script>

<template>
  <WorkbenchShell :title="t('nav.orgsManage')">
    <template #toolbar>
      <SearchFilterBar
        :keyword="keyword"
        :placeholder="t('admin.orgs.search')"
        @update:keyword="keyword = $event"
        @search="onSearch"
        @reset="onSearch"
      >
        <Select
          :model-value="status"
          @update:model-value="
            (value) => {
              status = value as typeof status
              onSearch()
            }
          "
        >
          <SelectTrigger class="h-9 w-[130px] text-[13px]">
            <SelectValue :placeholder="t('admin.orgs.status')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('common.allStatus') }}</SelectItem>
            <SelectItem value="active">{{ t('admin.orgs.statusActive') }}</SelectItem>
            <SelectItem value="disbanded">{{ t('admin.orgs.statusDisbanded') }}</SelectItem>
          </SelectContent>
        </Select>
        <template #actions>
          <Button size="toolbar" @click="openCreate">
            <Plus class="size-4" />
            {{ t('admin.orgs.create') }}
          </Button>
          <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
        </template>
      </SearchFilterBar>
    </template>

    <PaginatedTable
      :columns="columns"
      :data="orgs"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      show-size-picker
      :empty-text="t('admin.orgs.empty')"
      :row-click="(row) => router.push(`/admin/orgs/${row.id}`)"
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
    >
      <template #pager-left>
        <span class="tabular-nums">{{ t('admin.orgs.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedTable>

    <Dialog v-model:open="createOpen">
      <DialogContent class="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>{{ t('orgs.create.title') }}</DialogTitle>
          <DialogDescription class="sr-only">{{ t('orgs.create.name') }}</DialogDescription>
        </DialogHeader>
        <form class="grid gap-4" @submit.prevent="submitCreate">
          <div class="grid gap-1.5">
            <Label for="admin-org-name" class="text-[13px]">
              {{ t('orgs.create.name') }}
              <span class="text-destructive" aria-hidden="true">*</span>
            </Label>
            <Input
              id="admin-org-name"
              v-model="form.name"
              maxlength="64"
              class="h-9 text-[13px]"
              :placeholder="t('orgs.create.namePlaceholder')"
            />
          </div>
          <div class="grid gap-1.5">
            <Label for="admin-org-desc" class="text-[13px]">{{ t('orgs.create.description') }}</Label>
            <Textarea
              id="admin-org-desc"
              v-model="form.description"
              rows="3"
              maxlength="2000"
              class="min-h-[84px] text-[13px]"
              :placeholder="t('orgs.create.descriptionPlaceholder')"
            />
          </div>
          <div class="grid gap-1.5">
            <Label for="admin-org-admins" class="text-[13px]">{{ t('orgs.create.adminIds') }}</Label>
            <Textarea
              id="admin-org-admins"
              v-model="form.adminIds"
              rows="3"
              class="min-h-[84px] font-mono text-[12.5px]"
              :placeholder="t('orgs.create.adminIdsPlaceholder')"
            />
            <p class="text-[12px] leading-5 text-muted-foreground">
              {{ t('orgs.create.adminIdsHint') }}
            </p>
          </div>
        </form>
        <DialogFooter>
          <Button variant="outline" size="sm" :disabled="creating" @click="createOpen = false">
            {{ t('action.cancel') }}
          </Button>
          <Button size="sm" :disabled="creating" @click="submitCreate">
            <Loader2 v-if="creating" class="size-4 animate-spin" />
            {{ t('orgs.create.title') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </WorkbenchShell>
</template>