<script setup lang="ts">
/**
 * 比赛详情 · 主页面板：公告条（Markdown，赛时可由管理角色更新）+ 比赛说明。
 */
import { useI18n } from 'vue-i18n'
import MarkdownView from '@/components/MarkdownView.vue'
import { formatDateTime } from '@/utils/format'
import type { ContestDetail } from '@/types'

defineProps<{
  detail: ContestDetail
}>()

const { t } = useI18n()
</script>

<template>
  <div class="pane-scroll">
    <!-- 公告条：赛时可由管理角色更新（Markdown） -->
    <n-alert v-if="detail.announcement" type="info" :bordered="false" class="announcement">
      <template #header>
        <div class="announcement__head">
          <span>{{ t('contests.detail.announcement') }}</span>
          <span v-if="detail.announcement_updated_at" class="announcement__time">
            {{ t('contests.detail.announcementUpdatedAt') }}
            {{ formatDateTime(detail.announcement_updated_at) }}
          </span>
        </div>
      </template>
      <MarkdownView :source="detail.announcement" />
    </n-alert>
    <section class="panel">
      <h4 class="panel__title">{{ t('contests.detail.about') }}</h4>
      <MarkdownView v-if="detail.description" :source="detail.description" class="home-desc" />
      <div v-else class="home-desc home-desc--empty">
        {{ t('contests.detail.noDescription') }}
      </div>
    </section>
  </div>
</template>

<style scoped>
/* pane 内滚动区：列表撑满，超出滚动 */
.pane-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ---- 主页面板 ---- */
.announcement {
  flex-shrink: 0;
}
.announcement__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}
.announcement__time {
  font-size: 12px;
  font-weight: 400;
  color: var(--app-text-secondary);
}

.panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 18px;
  border: 1px solid var(--app-border);
  border-radius: 0;
  background: var(--app-card-bg, #fff);
  overflow: auto;
}
.panel__title {
  margin: 0;
  font-size: 13px;
  font-weight: 650;
  color: var(--app-text);
  display: flex;
  align-items: center;
  gap: 8px;
}
.panel__title::before {
  content: '';
  width: 3px;
  height: 14px;
  border-radius: 2px;
  background: var(--app-primary);
}
.home-desc {
  margin: 0;
  font-size: 13px;
  color: var(--app-text);
}
.home-desc--empty {
  color: var(--app-text-secondary);
  padding: 22px 0;
  text-align: center;
}

/* ---- 窄屏 ---- */
@media (max-width: 900px) {
  .pane-scroll {
    overflow: visible;
  }
}
</style>
