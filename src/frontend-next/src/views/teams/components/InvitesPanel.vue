<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Copy, Loader2, MailPlus } from '@lucide/vue'

import { createTeamInvite, listTeamApplications, reviewTeamApplication } from '@/api/teams'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { usePagination } from '@/composables/usePagination'
import { copyToClipboard } from '@/utils/clipboard'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { TeamApplicationItem } from '@/types'

const props = defineProps<{ teamId: string }>()

const emit = defineEmits<{ 'members-changed': [] }>()

const { t } = useI18n()

// ---- 邀请链接（多人可用、有效期内在邀请落地页可提交申请） ----
const invite = reactive({ token: '', expiresAt: '' })
const inviting = ref(false)

const inviteLink = computed(() =>
  invite.token ? `${window.location.origin}/teams/invites/${invite.token}` : '',
)

async function createInvite(): Promise<void> {
  if (inviting.value) return
  inviting.value = true
  try {
    const result = await createTeamInvite(props.teamId)
    invite.token = result.token
    invite.expiresAt = formatDateTime(result.expires_at)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    inviting.value = false
  }
}

async function copyInviteLink(): Promise<void> {
  const ok = await copyToClipboard(inviteLink.value)
  if (ok) message.success(t('common.copied'))
  else message.error(t('common.copyFailed'))
}

// ---- 待审申请 ----
const applications = ref<TeamApplicationItem[]>([])
const loading = ref(false)
const reviewingId = ref('')
const { page, pageSize, total, changePage, beginLoad, isCurrent } = usePagination()

async function loadApplications(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listTeamApplications(props.teamId, {
      page: page.value,
      page_size: pageSize.value,
    })
    if (!isCurrent(seq)) return
    applications.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

function onPageChange(value: number): void {
  changePage(value)
  void loadApplications()
}

async function review(row: TeamApplicationItem, approve: boolean): Promise<void> {
  if (reviewingId.value) return
  reviewingId.value = row.id
  try {
    await reviewTeamApplication(props.teamId, row.id, approve)
    message.success(
      t(approve ? 'teams.applications.approveSuccess' : 'teams.applications.rejectSuccess'),
    )
    await loadApplications()
    if (approve) emit('members-changed')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    reviewingId.value = ''
  }
}

const columns = computed<AppTableColumn<TeamApplicationItem>[]>(() => [
  {
    key: 'applicant',
    title: t('teams.applications.applicant'),
    cell: (row) =>
      h('div', { class: 'flex min-w-0 items-center gap-2.5 py-0.5' }, [
        h(BaseAvatar, { name: row.nickname, size: 30 }),
        h('span', { class: 'truncate text-[13px] font-medium' }, row.nickname),
      ]),
  },
  {
    key: 'source',
    title: t('teams.applications.source'),
    width: '120px',
    cell: (row) =>
      row.invite_token
        ? h(ToneBadge, { tone: 'info', label: t('teams.applications.viaInvite') })
        : h(ToneBadge, { tone: 'default', label: t('teams.applications.direct') }),
  },
  {
    key: 'applied_at',
    title: t('teams.applications.appliedAt'),
    width: '170px',
    cell: (row) => formatDateTime(row.applied_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'ops',
    width: '150px',
    align: 'right',
    cell: (row) => {
      const busy = reviewingId.value === row.id
      return h('div', { class: 'flex items-center justify-end gap-1.5' }, [
        h(
          Button,
          {
            size: 'xs',
            disabled: Boolean(reviewingId.value),
            onClick: () => review(row, true),
          },
          { default: () => t('teams.applications.approve') },
        ),
        h(
          Button,
          {
            size: 'xs',
            variant: 'outline',
            disabled: Boolean(reviewingId.value),
            onClick: () => review(row, false),
          },
          {
            default: () => [
              busy ? h(Loader2, { class: 'size-3 animate-spin' }) : null,
              t('teams.applications.reject'),
            ],
          },
        ),
      ])
    },
  },
])

onMounted(loadApplications)
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3">
    <section class="shrink-0 rounded-xl border border-border bg-card px-4 py-3.5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <h2 class="text-[13.5px] font-semibold">{{ t('teams.settings.inviteTitle') }}</h2>
          <p class="mt-1 max-w-[78ch] text-[12px] leading-5 text-muted-foreground">
            {{ t('teams.settings.inviteHint') }}
          </p>
        </div>
        <Button size="sm" :disabled="inviting" @click="createInvite">
          <Loader2 v-if="inviting" class="size-4 animate-spin" />
          <MailPlus v-else class="size-4" />
          {{ invite.token ? t('teams.settings.regenerate') : t('teams.settings.generateInvite') }}
        </Button>
      </div>

      <div v-if="invite.token" class="mt-3 flex flex-wrap items-center gap-2">
        <Input
          :model-value="inviteLink"
          readonly
          class="h-9 min-w-[260px] flex-1 font-mono text-[12px]"
          @focus="($event.target as HTMLInputElement).select()"
        />
        <Button variant="outline" size="toolbar" @click="copyInviteLink">
          <Copy class="size-3.5" />
          {{ t('action.copyLink') }}
        </Button>
        <span class="text-[11.5px] tabular-nums text-muted-foreground">
          {{ t('teams.settings.inviteExpiry', { time: invite.expiresAt }) }}
        </span>
      </div>
    </section>

    <section class="flex min-h-0 flex-1 flex-col gap-2">
      <h2 class="shrink-0 text-[13.5px] font-semibold">
        {{ t('teams.detail.tabApplications') }}
      </h2>
      <PaginatedTable
        :columns="columns"
        :data="applications"
        :loading="loading"
        :total="total"
        :page="page"
        :page-size="pageSize"
        :empty-text="t('teams.applications.empty')"
        @update:page="onPageChange"
      >
        <template #pager-left>
          <span class="tabular-nums">{{ t('teams.stats.pending') }} · {{ total }}</span>
        </template>
      </PaginatedTable>
    </section>
  </div>
</template>
