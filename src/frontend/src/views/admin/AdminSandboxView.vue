<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Refresh } from '@element-plus/icons-vue'

import * as adminApi from '@/api/admin'
import type { SandboxNode } from '@/types'
import { SANDBOX_STATUS, toNaiveTagType } from '@/constants/dict'
import { formatDateTime } from '@/utils/format'
import { message } from '@/utils/feedback'

const { t } = useI18n()
const loading = ref(false)
const nodes = ref<SandboxNode[]>([])
async function load() {
  loading.value = true
  try {
    nodes.value = await adminApi.adminSandboxStatus()
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}
onMounted(load)
const onlineCount = computed(() => nodes.value.filter((n) => n.status === 'online').length)
const totalLoad = computed(() => {
  const online = nodes.value.filter((n) => n.status === 'online')
  return online.length ? online.reduce((s, n) => s + n.load, 0) / online.length : 0
})

function loadColor(load: number): string {
  if (load > 0.8) return '#d03050'
  if (load > 0.5) return '#f0a020'
  return '#18a058'
}
</script>

<template>
  <div class="page-stack">
    <n-card :bordered="false">
      <template #header>
        <div class="sandbox-head">
          <span>{{ t('admin.sandbox.title') }}</span>
          <div class="sandbox-summary">
            <n-tag type="success" :bordered="false" round>
              {{ t('admin.sandbox.online', { online: onlineCount, total: nodes.length }) }}
            </n-tag>
            <n-tag type="info" :bordered="false" round>
              {{ t('admin.sandbox.avgLoad', { load: (totalLoad * 100).toFixed(0) }) }}
            </n-tag>
          </div>
        </div>
      </template>
      <template #header-extra>
        <n-button size="small" secondary :loading="loading" @click="load">
          <template #icon>
            <n-icon :component="Refresh" />
          </template>
          {{ t('action.refresh') }}
        </n-button>
      </template>

      <n-spin :show="loading">
        <div v-if="nodes.length" class="node-grid">
          <n-card
            v-for="node in nodes"
            :key="node.name"
            size="small"
            class="node-card"
            embedded
          >
            <div class="node-head">
              <code>{{ node.name }}</code>
              <n-tag
                size="small"
                round
                :type="toNaiveTagType(SANDBOX_STATUS[node.status]?.tag ?? 'info')"
              >
                {{ SANDBOX_STATUS[node.status]?.label ?? node.status }}
              </n-tag>
            </div>
            <div class="node-metric">
              <span>{{ t('admin.sandbox.load') }}</span>
              <n-progress
                type="line"
                :percentage="Math.round(node.load * 100)"
                :height="8"
                :color="loadColor(node.load)"
                :show-indicator="true"
              />
            </div>
            <div class="node-stats">
              <span>CPU {{ node.cpu_usage }}%</span>
              <span>{{ t('admin.sandbox.memory') }} {{ node.memory_usage }}%</span>
              <span>{{ t('admin.sandbox.tasks') }} {{ node.running_tasks }}</span>
            </div>
            <div class="node-foot">
              <span class="node-version">{{ t('admin.sandbox.version') }}: {{ node.version }}</span>
              <span class="node-heartbeat">{{ formatDateTime(node.last_heartbeat_at) }}</span>
            </div>
          </n-card>
        </div>
        <n-empty v-else-if="!loading" :description="t('admin.sandbox.empty')" />
      </n-spin>
    </n-card>
  </div>
</template>

<style scoped>
.sandbox-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.sandbox-summary {
  display: flex;
  gap: 8px;
}
.node-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}
.node-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.node-metric {
  display: grid;
  gap: 6px;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.node-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.node-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed var(--app-border);
  font-size: 11px;
  color: var(--app-text-secondary);
}
.node-version {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
