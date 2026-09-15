<script setup lang="ts">
/**
 * 赛时工具页：公告编辑 + 赛后解榜 + 滚榜大屏 + 快捷入口。
 * 管理后台 `/admin/contests/:cid/tools`；团队空间 `/teams/:teamId/contests/:cid/tools`。
 * 结构性字段编辑走编辑向导（赛中被后端状态守卫拒绝，docs/contracts/contests.md）。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { CopyDocument } from '@element-plus/icons-vue'

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
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { goBackOrFallback } from '@/utils/navigation'
import { copyToClipboard } from '@/utils/clipboard'
import { formatDateTime } from '@/utils/format'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import type { ContestDetail } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const contestId = computed(() => String(route.params.cid))
const teamId = computed(() => (route.params.teamId ? String(route.params.teamId) : null))
const loading = ref(false)
const contest = ref<ContestDetail | null>(null)

const announcementDraft = ref('')
const announcementSaving = ref(false)
const unfreezing = ref(false)
const extending = ref(false)
const freezeSaving = ref(false)
const freezeDraft = ref<number | null>(null)
const nowTick = ref(Date.now())
let clockTimer: number | null = null

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
const listFallback = computed(() => (teamId.value ? `/teams/${teamId.value}` : '/admin/contests'))

const statusMap = computed(() => ({
  running: { label: t('contests.statusRunning'), type: 'success' as const },
  scheduled: { label: t('contests.statusScheduled'), type: 'info' as const },
  finished: { label: t('contests.statusFinished'), type: 'default' as const },
}))

function pad(n: number) {
  return String(n).padStart(2, '0')
}

function formatRemain(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  if (days > 0) {
    return `${days}${t('contests.detail.unitDay')} ${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
  }
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
}

const countdown = computed(() => {
  const d = contest.value
  if (!d) return { label: t('contests.tools.countdown'), value: '—' }
  const now = nowTick.value
  const start = new Date(d.start_time).getTime()
  const end = new Date(d.end_time).getTime()
  if (d.status === 'finished' || now >= end) {
    return { label: t('contests.detail.contestOver'), value: '—' }
  }
  if (d.status === 'running' || now >= start) {
    return { label: t('contests.detail.endsIn'), value: formatRemain(end - now) }
  }
  return { label: t('contests.detail.startsIn'), value: formatRemain(start - now) }
})

const unfreezeDisabledHint = computed(() => {
  if (canUnfreeze.value) return ''
  if (!isAfterContest.value) return t('contests.tools.unfreezeDisabledNotFinished')
  return t('contests.tools.unfreezeDisabledNotFrozen')
})

function backToList() {
  goBackOrFallback(router, listFallback.value)
}

function startClock() {
  if (clockTimer !== null) return
  clockTimer = window.setInterval(() => {
    nowTick.value = Date.now()
  }, 1000)
}

function stopClock() {
  if (clockTimer === null) return
  window.clearInterval(clockTimer)
  clockTimer = null
}

async function load() {
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

async function saveAnnouncement() {
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

async function doUnfreeze() {
  unfreezing.value = true
  try {
    await confirmAsyncDialog({
      title: t('contests.detail.unfreeze'),
      content: t('contests.detail.unfreezeConfirm'),
      positiveText: t('contests.detail.unfreeze'),
      action: () =>
        teamId.value
          ? unfreezeTeamContestBoard(teamId.value, contestId.value)
          : unfreezeContestBoard(contestId.value),
      successMessage: t('common.success'),
      onAfterSuccess: async () => {
        contest.value = await (teamId.value
          ? getTeamContest(teamId.value, contestId.value)
          : getContest(contestId.value))
      },
    })
  } finally {
    unfreezing.value = false
  }
}

function openScrollboard() {
  const qs = new URLSearchParams({ contest_id: contestId.value })
  if (teamId.value) qs.set('team_id', teamId.value)
  window.open(`/scrollboard.html?${qs.toString()}`, '_blank')
}

function openContest() {
  void router.push(contextBase.value)
}

function openBoard() {
  void router.push({ path: contextBase.value, query: { tab: 'board' } })
}

function openSubmissions() {
  void router.push({ path: contextBase.value, query: { tab: 'submissions' } })
}

function openEdit() {
  if (!canPreEdit.value) return
  void router.push(editPath.value)
}

async function reloadContest() {
  contest.value = await (teamId.value
    ? getTeamContest(teamId.value, contestId.value)
    : getContest(contestId.value))
  announcementDraft.value = contest.value.announcement ?? ''
  freezeDraft.value = contest.value.freeze_time
    ? new Date(contest.value.freeze_time).getTime()
    : null
}

function extendTargetIso(extraMs: number): string {
  const currentEnd = contest.value ? Date.parse(contest.value.end_time) : Date.now()
  return new Date(Math.max(currentEnd, Date.now()) + extraMs).toISOString()
}

async function doExtend(endIso: string) {
  if (!canExtend.value) return
  extending.value = true
  try {
    await confirmAsyncDialog({
      title: t('contests.tools.extend'),
      content: t('contests.tools.extendConfirm', { time: formatDateTime(endIso) }),
      positiveText: t('contests.tools.extend'),
      action: () =>
        teamId.value
          ? extendTeamContest(teamId.value, contestId.value, endIso)
          : extendContest(contestId.value, endIso),
      successMessage: t('common.success'),
      onAfterSuccess: () => reloadContest(),
    })
  } finally {
    extending.value = false
  }
}

async function saveFreezeTime() {
  if (!canAdjustFreeze.value) return
  const iso = freezeDraft.value == null ? null : new Date(freezeDraft.value).toISOString()
  const dueNow = iso != null && contest.value?.status === 'running' && Date.parse(iso) <= Date.now()
  const run = async () => {
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
  if (dueNow) {
    await confirmAsyncDialog({
      title: t('contests.tools.freezeAt'),
      content: t('contests.tools.freezeNowConfirm'),
      positiveText: t('contests.tools.freezeSave'),
      action: async () => {
        await (teamId.value
          ? updateTeamContestFreezeTime(teamId.value, contestId.value, iso)
          : updateContestFreezeTime(contestId.value, iso))
      },
      successMessage: t('common.success'),
      onAfterSuccess: () => reloadContest(),
    })
    return
  }
  await run()
}

async function copyContestLink() {
  const url = `${window.location.origin}${contextBase.value}`
  const ok = await copyToClipboard(url)
  if (ok) message.success(t('contests.tools.copied'))
  else message.error(t('common.copyFailed'))
}

onMounted(() => {
  void load()
  startClock()
})
onBeforeUnmount(stopClock)
</script>

<template>
  <WorkbenchShell>
    <template #header>
      <div class="tools-head">
        <strong class="tools-head__title">{{ t('contests.tools.title') }}</strong>
        <span v-if="contest" class="tools-head__contest">{{ contest.title }}</span>
        <n-tag v-if="contest" size="small" :bordered="false" :type="statusMap[contest.status].type">
          {{ statusMap[contest.status].label }}
        </n-tag>
        <n-tag v-if="contest?.board_frozen" size="small" type="warning" :bordered="false">
          {{ t('contests.boardFrozenTag') }}
        </n-tag>
      </div>
    </template>
    <template #header-extra>
      <div class="tools-head__extra">
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
        <n-button size="small" secondary @click="openContest">
          {{ t('contests.tools.openContest') }}
        </n-button>
        <n-button size="small" secondary @click="backToList">
          {{ teamId ? t('contests.list.backToTeam') : t('contests.list.backToList') }}
        </n-button>
      </div>
    </template>

    <n-spin :show="loading" class="tools-spin">
      <div v-if="contest" class="tools-body">
        <section class="tools-stats">
          <div class="stat">
            <span class="stat__label">{{ countdown.label }}</span>
            <strong class="stat__value stat__value--clock">{{ countdown.value }}</strong>
          </div>
          <div class="stat">
            <span class="stat__label">{{ t('contests.detail.registeredCount') }}</span>
            <strong class="stat__value">{{ contest.registered_count }}</strong>
          </div>
          <div class="stat">
            <span class="stat__label">{{ t('contests.detail.problems') }}</span>
            <strong class="stat__value">{{ contest.problem_count }}</strong>
          </div>
          <div class="stat">
            <span class="stat__label">{{ t('contests.tools.freezeAt') }}</span>
            <strong class="stat__value stat__value--sm">
              {{
                contest.freeze_time
                  ? formatDateTime(contest.freeze_time)
                  : t('contests.tools.noFreeze')
              }}
            </strong>
          </div>
          <div class="stat stat--action">
            <n-button size="small" secondary @click="copyContestLink">
              <template #icon>
                <n-icon :component="CopyDocument" />
              </template>
              {{ t('contests.tools.copyLink') }}
            </n-button>
          </div>
        </section>

        <div class="tools-grid">
          <section class="tools-card tools-card--announce">
            <h4 class="tools-card__title">{{ t('contests.tools.announcement') }}</h4>
            <p class="tools-card__hint">
              {{
                contest.status === 'scheduled'
                  ? t('contests.tools.announcementPrepare')
                  : t('contests.tools.announcementHint')
              }}
            </p>
            <MarkdownEditor
              v-model="announcementDraft"
              compact
              min-height="280px"
              :placeholder="t('contests.tools.announcementPlaceholder')"
            />
            <div class="tools-card__actions">
              <n-button
                type="primary"
                size="small"
                :loading="announcementSaving"
                :disabled="!announcementDirty"
                @click="saveAnnouncement"
              >
                {{ t('action.save') }}
              </n-button>
              <span v-if="contest.announcement_updated_at" class="tools-card__meta">
                {{ t('contests.detail.announcementUpdatedAt') }}
                {{ formatDateTime(contest.announcement_updated_at) }}
              </span>
            </div>
            <div v-if="announcementDraft.trim()" class="tools-card__preview">
              <p class="tools-card__preview-label">{{ t('contests.tools.preview') }}</p>
              <MarkdownView :source="announcementDraft" />
            </div>
          </section>

          <div class="tools-side">
            <section class="tools-card">
              <h4 class="tools-card__title">{{ t('contests.tools.schedule') }}</h4>
              <p class="tools-card__hint">{{ t('contests.tools.extendHint') }}</p>
              <p class="tools-card__meta">
                {{ t('contests.tools.currentEnd') }}
                {{ formatDateTime(contest.end_time) }}
              </p>
              <div class="tools-links">
                <n-button
                  size="small"
                  secondary
                  :disabled="!canExtend"
                  :loading="extending"
                  @click="doExtend(extendTargetIso(15 * 60 * 1000))"
                >
                  {{ t('contests.tools.extendBy15') }}
                </n-button>
                <n-button
                  size="small"
                  secondary
                  :disabled="!canExtend"
                  :loading="extending"
                  @click="doExtend(extendTargetIso(30 * 60 * 1000))"
                >
                  {{ t('contests.tools.extendBy30') }}
                </n-button>
                <n-button
                  size="small"
                  secondary
                  :disabled="!canExtend"
                  :loading="extending"
                  @click="doExtend(extendTargetIso(60 * 60 * 1000))"
                >
                  {{ t('contests.tools.extendBy60') }}
                </n-button>
              </div>
              <p v-if="!canExtend" class="tools-card__meta">
                {{ t('contests.tools.extendDisabled') }}
              </p>
              <p class="tools-card__hint">{{ t('contests.tools.freezeHint') }}</p>
              <n-date-picker
                v-model:value="freezeDraft"
                type="datetime"
                clearable
                :disabled="!canAdjustFreeze"
                style="width: 100%"
              />
              <n-button
                size="small"
                secondary
                :disabled="!canAdjustFreeze"
                :loading="freezeSaving"
                @click="saveFreezeTime"
              >
                {{ t('contests.tools.freezeSave') }}
              </n-button>
              <p v-if="!canAdjustFreeze" class="tools-card__meta">
                {{
                  contest.board_frozen
                    ? t('contests.tools.freezeDisabledFrozen')
                    : t('contests.tools.freezeDisabledFinished')
                }}
              </p>
            </section>

            <section class="tools-card">
              <h4 class="tools-card__title">{{ t('contests.tools.boardOps') }}</h4>
              <p class="tools-card__hint">{{ t('contests.tools.unfreezeHint') }}</p>
              <n-button
                type="warning"
                secondary
                :disabled="!canUnfreeze"
                :loading="unfreezing"
                @click="doUnfreeze"
              >
                {{ t('contests.detail.unfreeze') }}
              </n-button>
              <p v-if="!canUnfreeze" class="tools-card__meta">{{ unfreezeDisabledHint }}</p>
            </section>

            <section class="tools-card">
              <h4 class="tools-card__title">{{ t('contests.tools.scrollboard') }}</h4>
              <p class="tools-card__hint">{{ t('contests.tools.scrollboardHint') }}</p>
              <n-button
                type="primary"
                secondary
                :disabled="!canScrollboard"
                @click="openScrollboard"
              >
                {{ t('contests.tools.scrollboardOpen') }}
              </n-button>
              <p v-if="!canScrollboard" class="tools-card__meta">
                {{ t('contests.tools.scrollboardDisabled') }}
              </p>
            </section>

            <section class="tools-card">
              <h4 class="tools-card__title">{{ t('contests.tools.shortcuts') }}</h4>
              <div class="tools-links">
                <n-button secondary size="small" @click="openBoard">
                  {{ t('contests.tools.openBoard') }}
                </n-button>
                <n-button secondary size="small" @click="openSubmissions">
                  {{ t('contests.tools.openSubmissions') }}
                </n-button>
                <n-button secondary size="small" :disabled="!canPreEdit" @click="openEdit">
                  {{ t('contests.tools.editContest') }}
                </n-button>
              </div>
            </section>
          </div>
        </div>
      </div>
    </n-spin>
  </WorkbenchShell>
</template>

<style scoped>
.tools-head {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.tools-head__title {
  font-size: 15px;
  font-weight: 650;
}
.tools-head__contest {
  color: var(--app-text-secondary);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tools-head__extra {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tools-spin {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.tools-spin :deep(.n-spin-container),
.tools-spin :deep(.n-spin-content) {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.tools-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
  flex: 1;
  overflow: auto;
}
.tools-stats {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: var(--app-muted-bg);
}
.stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.stat__label {
  font-size: 12px;
  color: var(--app-text-secondary);
}
.stat__value {
  font-size: 18px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}
.stat__value--clock {
  letter-spacing: 0.02em;
}
.stat__value--sm {
  font-size: 13px;
  font-weight: 600;
}
.stat--action {
  justify-content: center;
  align-items: flex-start;
}
.tools-grid {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(240px, 2fr);
  gap: 16px;
  align-items: start;
  flex: 1;
  min-height: 0;
}
.tools-side {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.tools-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 18px;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: var(--app-card-bg, #fff);
}
.tools-card--announce {
  min-height: 0;
}
.tools-card__title {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
}
.tools-card__hint {
  margin: 0;
  font-size: 12px;
  color: var(--app-text-secondary);
  line-height: 1.6;
}
.tools-card__actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.tools-card__meta {
  margin: 0;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.tools-card__preview {
  padding: 12px 14px;
  border: 1px dashed var(--app-border);
  border-radius: 8px;
  font-size: 13px;
}
.tools-card__preview-label {
  margin: 0 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--app-text-secondary);
}
.tools-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
@media (max-width: 900px) {
  .tools-stats {
    grid-template-columns: 1fr 1fr;
  }
  .tools-grid {
    grid-template-columns: 1fr;
  }
}
</style>
