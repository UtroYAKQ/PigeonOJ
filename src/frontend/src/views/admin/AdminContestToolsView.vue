<script setup lang="ts">
/**
 * 赛时工具页（管理后台 /admin/contests/:cid/tools）：
 * 公告编辑（赛时唯一受控编辑出口）+ 赛后解榜 + 滚榜大屏入口。
 * 入口在比赛管理列表行内按钮（比赛开始后显示）；结构性字段编辑走编辑向导
 * （赛中被后端状态守卫拒绝，docs/contracts/contests.md「状态守卫与赛时工具」）。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import {
  getContest,
  unfreezeContestBoard,
  updateContestAnnouncement,
} from '@/api/contests'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { goBackOrFallback } from '@/utils/navigation'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import { formatDateTime } from '@/utils/format'
import type { ContestDetail } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const contestId = computed(() => String(route.params.cid))
const loading = ref(false)
const contest = ref<ContestDetail | null>(null)

const announcementDraft = ref('')
const announcementSaving = ref(false)
const unfreezing = ref(false)

const isAfterContest = computed(() => contest.value?.status === 'finished')
const canUnfreeze = computed(() => Boolean(contest.value?.board_frozen && isAfterContest.value))

const statusMap = computed(() => ({
  running: { label: t('contests.statusRunning'), type: 'success' as const },
  scheduled: { label: t('contests.statusScheduled'), type: 'info' as const },
  finished: { label: t('contests.statusFinished'), type: 'default' as const },
}))

function backToList() {
  goBackOrFallback(router, '/admin/contests')
}

async function load() {
  loading.value = true
  try {
    contest.value = await getContest(contestId.value)
    announcementDraft.value = contest.value.announcement ?? ''
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
    await updateContestAnnouncement(contestId.value, announcementDraft.value)
    message.success(t('common.success'))
    contest.value = await getContest(contestId.value)
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
      action: () => unfreezeContestBoard(contestId.value),
      successMessage: t('common.success'),
      onAfterSuccess: async () => {
        contest.value = await getContest(contestId.value)
      },
    })
  } finally {
    unfreezing.value = false
  }
}

/** 滚榜（赛后大屏工具）：新窗口打开独立 HTML，读同源 localStorage token 鉴权 */
function openScrollboard() {
  window.open(`/scrollboard.html?contest_id=${contestId.value}`, '_blank')
}

onMounted(load)
</script>

<template>
  <WorkbenchShell>
    <template #header>
      <div class="tools-head">
        <strong class="tools-head__title">{{ t('contests.tools.title') }}</strong>
        <span v-if="contest" class="tools-head__contest">{{ contest.title }}</span>
        <n-tag
          v-if="contest"
          size="small"
          :bordered="false"
          :type="statusMap[contest.status].type"
        >
          {{ statusMap[contest.status].label }}
        </n-tag>
        <n-tag v-if="contest?.board_frozen" size="small" type="warning" :bordered="false">
          {{ t('contests.boardFrozenTag') }}
        </n-tag>
      </div>
    </template>
    <template #header-extra>
      <n-button size="small" secondary @click="backToList">
        {{ t('contests.list.backToList') }}
      </n-button>
    </template>

    <n-spin :show="loading" class="tools-spin">
      <div v-if="contest" class="tools-grid">
        <!-- 公告：赛时可改，主页 tab 顶部公告条对参赛者展示 -->
        <section class="tools-card">
          <h4 class="tools-card__title">{{ t('contests.tools.announcement') }}</h4>
          <p class="tools-card__hint">{{ t('contests.tools.announcementHint') }}</p>
          <n-input
            v-model:value="announcementDraft"
            type="textarea"
            :rows="8"
            maxlength="4096"
            show-count
            :placeholder="t('contests.tools.announcementPlaceholder')"
          />
          <div class="tools-card__actions">
            <n-button
              type="primary"
              size="small"
              :loading="announcementSaving"
              @click="saveAnnouncement"
            >
              {{ t('action.save') }}
            </n-button>
            <span v-if="contest.announcement_updated_at" class="tools-card__meta">
              {{ t('contests.detail.announcementUpdatedAt') }}
              {{ formatDateTime(contest.announcement_updated_at) }}
            </span>
          </div>
          <div v-if="contest.announcement" class="tools-card__preview">
            <p class="tools-card__preview-label">{{ t('contests.tools.preview') }}</p>
            <MarkdownView :source="contest.announcement" />
          </div>
        </section>

        <!-- 解榜：赛后专用（从提交记录权威重算，回填封榜期结果） -->
        <section class="tools-card">
          <h4 class="tools-card__title">{{ t('contests.tools.unfreeze') }}</h4>
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
        </section>

        <!-- 滚榜：赛后颁奖大屏回放 -->
        <section class="tools-card">
          <h4 class="tools-card__title">{{ t('contests.tools.scrollboard') }}</h4>
          <p class="tools-card__hint">{{ t('contests.tools.scrollboardHint') }}</p>
          <n-button type="primary" secondary @click="openScrollboard">
            {{ t('contests.tools.scrollboardOpen') }}
          </n-button>
        </section>
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
.tools-spin {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.tools-spin :deep(.n-spin-container),
.tools-spin :deep(.n-spin-content) {
  height: 100%;
}
.tools-grid {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 16px;
  align-items: start;
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
/* 解榜 / 滚榜叠放在公告卡下（窄屏逐级降列） */
.tools-card:nth-child(2),
.tools-card:nth-child(3) {
  grid-column: 2;
}
@media (max-width: 900px) {
  .tools-grid {
    grid-template-columns: 1fr;
  }
  .tools-card:nth-child(2),
  .tools-card:nth-child(3) {
    grid-column: auto;
  }
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
</style>
