<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import {
  extendContest,
  getContest,
  unfreezeContestBoard,
  updateContestAnnouncement,
  updateContestFreezeTime,
} from '@/api/contests'
import {
  extendTeamContest,
  getTeamContest,
  unfreezeTeamContestBoard,
  updateTeamContestAnnouncement,
  updateTeamContestFreezeTime,
} from '@/api/teams'
import RefreshButton from '@/components/common/RefreshButton.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import { Button } from '@/components/ui/button'
import { copyToClipboard } from '@/utils/clipboard'
import { confirmDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import { goBackOrFallback } from '@/utils/navigation'
import type { ContestDetail } from '@/types'
import ContestAnnouncementCard from './contest-components/ContestAnnouncementCard.vue'
import ContestBoardOpsCard from './contest-components/ContestBoardOpsCard.vue'
import ContestScheduleCard from './contest-components/ContestScheduleCard.vue'
import ContestScrollboardCard from './contest-components/ContestScrollboardCard.vue'
import ContestShortcutsCard from './contest-components/ContestShortcutsCard.vue'
import ContestStatusBadge from '@/components/contests/ContestStatusBadge.vue'
import ContestToolsStats from './contest-components/ContestToolsStats.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const contestId = computed(() => String(route.params.cid))
const teamId = computed(() => (route.params.teamId ? String(route.params.teamId) : null))
const listFallback = computed(() => (teamId.value ? `/teams/${teamId.value}` : '/admin/contests'))
const contextBase = computed(() =>
  teamId.value
    ? `/teams/${teamId.value}/contests/${contestId.value}`
    : `/contests/${contestId.value}`,
)
const editPath = computed(() =>
  teamId.value
    ? `/teams/${teamId.value}/contests/${contestId.value}/edit/basic`
    : `/admin/contests/${contestId.value}/edit/basic`,
)

const loading = ref(false)
const contest = ref<ContestDetail | null>(null)

const announcementDraft = ref('')
const announcementSaving = ref(false)
const unfreezing = ref(false)
const freezeSaving = ref(false)
const freezeDraft = ref<number | null>(null)
/** 正在延时的分钟数（null = 空闲） */
const extendingMinutes = ref<number | null>(null)

const isAfterContest = computed(() => contest.value?.status === 'finished')
const canUnfreeze = computed(() => Boolean(contest.value?.board_frozen && isAfterContest.value))
const canScrollboard = computed(() => isAfterContest.value)
const canPreEdit = computed(() => contest.value?.status === 'scheduled')
const canExtend = computed(
  () => contest.value?.status === 'running' || contest.value?.status === 'finished',
)
const canAdjustFreeze = computed(
  () =>
    Boolean(contest.value) && contest.value?.status !== 'finished' && !contest.value?.board_frozen,
)
const announcementDirty = computed(
  () => announcementDraft.value !== (contest.value?.announcement ?? ''),
)

const unfreezeDisabledHint = computed(() => {
  if (canUnfreeze.value) return ''
  if (!isAfterContest.value) return t('contests.tools.unfreezeDisabledNotFinished')
  return t('contests.tools.unfreezeDisabledNotFrozen')
})

async function reloadContest(): Promise<void> {
  const detail = await (teamId.value
    ? getTeamContest(teamId.value, contestId.value)
    : getContest(contestId.value))
  contest.value = detail
  announcementDraft.value = detail.announcement ?? ''
  freezeDraft.value = detail.freeze_time ? new Date(detail.freeze_time).getTime() : null
}

async function load(): Promise<void> {
  loading.value = true
  try {
    await reloadContest()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
    backToList()
  } finally {
    loading.value = false
  }
}

async function saveAnnouncement(): Promise<void> {
  if (!announcementDirty.value || announcementSaving.value) return
  announcementSaving.value = true
  try {
    await (teamId.value
      ? updateTeamContestAnnouncement(teamId.value, contestId.value, announcementDraft.value)
      : updateContestAnnouncement(contestId.value, announcementDraft.value))
    message.success(t('common.success'))
    await reloadContest()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    announcementSaving.value = false
  }
}

async function doUnfreeze(): Promise<void> {
  if (!canUnfreeze.value || unfreezing.value) return
  const ok = await confirmDialog({
    title: t('contests.detail.unfreeze'),
    content: t('contests.detail.unfreezeConfirm'),
    positiveText: t('contests.detail.unfreeze'),
    negativeText: t('action.cancel'),
  })
  if (!ok) return
  unfreezing.value = true
  try {
    await (teamId.value
      ? unfreezeTeamContestBoard(teamId.value, contestId.value)
      : unfreezeContestBoard(contestId.value))
    message.success(t('common.success'))
    await reloadContest()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    unfreezing.value = false
  }
}

function extendTargetIso(extraMinutes: number): string {
  const currentEnd = contest.value ? Date.parse(contest.value.end_time) : Date.now()
  const base = Number.isNaN(currentEnd) ? Date.now() : currentEnd
  return new Date(Math.max(base, Date.now()) + extraMinutes * 60 * 1000).toISOString()
}

async function doExtend(extraMinutes: number): Promise<void> {
  if (!canExtend.value || extendingMinutes.value !== null) return
  const endIso = extendTargetIso(extraMinutes)
  const ok = await confirmDialog({
    title: t('contests.tools.extend'),
    content: t('contests.tools.extendConfirm', { time: formatDateTime(endIso) }),
    positiveText: t('contests.tools.extend'),
    negativeText: t('action.cancel'),
  })
  if (!ok) return
  extendingMinutes.value = extraMinutes
  try {
    await (teamId.value
      ? extendTeamContest(teamId.value, contestId.value, endIso)
      : extendContest(contestId.value, endIso))
    message.success(t('common.success'))
    await reloadContest()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    extendingMinutes.value = null
  }
}

async function saveFreezeTime(): Promise<void> {
  if (!canAdjustFreeze.value || freezeSaving.value) return
  const iso = freezeDraft.value == null ? null : new Date(freezeDraft.value).toISOString()
  const dueNow = iso != null && contest.value?.status === 'running' && Date.parse(iso) <= Date.now()
  if (dueNow) {
    const ok = await confirmDialog({
      title: t('contests.tools.freezeAt'),
      content: t('contests.tools.freezeNowConfirm'),
      positiveText: t('contests.tools.freezeSave'),
      negativeText: t('action.cancel'),
    })
    if (!ok) return
  }
  freezeSaving.value = true
  try {
    await (teamId.value
      ? updateTeamContestFreezeTime(teamId.value, contestId.value, iso)
      : updateContestFreezeTime(contestId.value, iso))
    message.success(t('common.success'))
    await reloadContest()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    freezeSaving.value = false
  }
}

async function copyContestLink(): Promise<void> {
  const url = `${window.location.origin}${contextBase.value}`
  const ok = await copyToClipboard(url)
  if (ok) message.success(t('contests.tools.copied'))
  else message.error(t('common.copyFailed'))
}

function backToList(): void {
  goBackOrFallback(router, listFallback.value)
}

function openContest(): void {
  void router.push(contextBase.value)
}

function openBoard(): void {
  void router.push({ path: contextBase.value, query: { tab: 'board' } })
}

function openSubmissions(): void {
  void router.push({ path: contextBase.value, query: { tab: 'submissions' } })
}

function openEdit(): void {
  if (!canPreEdit.value) return
  void router.push(editPath.value)
}

function openScrollboard(): void {
  const query = new URLSearchParams({ contest_id: contestId.value })
  if (teamId.value) query.set('team_id', teamId.value)
  window.open(`/scrollboard.html?${query.toString()}`, '_blank', 'noopener')
}

onMounted(() => {
  void load()
})
</script>

<template>
  <WorkbenchShell>
    <template #title>
      <div class="flex min-w-0 flex-wrap items-center gap-2">
        <h1 class="text-xl font-semibold leading-tight tracking-tight">
          {{ t('contests.tools.title') }}
        </h1>
        <span v-if="contest" class="min-w-0 truncate text-[13px] text-muted-foreground">
          {{ contest.title }}
        </span>
        <ContestStatusBadge v-if="contest" :status="contest.status" />
        <ToneBadge
          v-if="contest?.board_frozen"
          tone="warning"
          :label="t('contests.boardFrozenTag')"
        />
      </div>
    </template>

    <template #actions>
      <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
      <Button variant="outline" size="sm" @click="openContest">
        {{ t('contests.tools.openContest') }}
      </Button>
      <Button variant="outline" size="sm" @click="backToList">
        {{ teamId ? t('contests.list.backToTeam') : t('contests.list.backToList') }}
      </Button>
    </template>

    <div v-if="loading && !contest" class="grid min-h-[360px] flex-1 place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else-if="contest" class="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
      <ContestToolsStats :contest="contest" @copy="copyContestLink" />

      <div class="grid items-start gap-3 xl:grid-cols-[minmax(0,3fr)_minmax(280px,2fr)]">
        <ContestAnnouncementCard
          v-model="announcementDraft"
          :status="contest.status"
          :saving="announcementSaving"
          :dirty="announcementDirty"
          :updated-at="contest.announcement_updated_at"
          @save="saveAnnouncement"
        />

        <div class="flex flex-col gap-3">
          <ContestScheduleCard
            v-model:freeze="freezeDraft"
            :contest="contest"
            :extending-minutes="extendingMinutes"
            :freeze-saving="freezeSaving"
            :can-extend="canExtend"
            :can-adjust-freeze="canAdjustFreeze"
            @extend="doExtend"
            @save-freeze="saveFreezeTime"
          />
          <ContestBoardOpsCard
            :can-unfreeze="canUnfreeze"
            :unfreezing="unfreezing"
            :disabled-hint="unfreezeDisabledHint"
            @unfreeze="doUnfreeze"
          />
          <ContestScrollboardCard :can-scrollboard="canScrollboard" @open="openScrollboard" />
          <ContestShortcutsCard
            :can-pre-edit="canPreEdit"
            @board="openBoard"
            @submissions="openSubmissions"
            @edit="openEdit"
          />
        </div>
      </div>
    </div>

    <div v-else class="grid flex-1 place-items-center text-[13px] text-muted-foreground">
      {{ t('common.loadFailed') }}
    </div>
  </WorkbenchShell>
</template>
