<script setup lang="ts">
/**
 * 沙箱节点状态（/admin/sandbox）：读 Redis 热数据展示在线节点负载 / CPU / 内存 / 运行任务。
 * 刷新按钮手动拉取；状态标签用共享 ToneBadge，负载条按阈值着色（>80% 危险 / >50% 警示）。
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Activity, Cpu, Loader2, MemoryStick, Server } from '@lucide/vue'

import * as adminApi from '@/api/admin'
import EmptyState from '@/components/common/EmptyState.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import { TONE_SOLID_CLASSES } from '@/components/common/tone'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import { SANDBOX_STATUS } from '@/constants/dict'
import { formatDateTime } from '@/utils/format'
import { message } from '@/utils/feedback'
import type { SandboxNode } from '@/types'

const { t } = useI18n()

const nodes = ref<SandboxNode[]>([])
const loading = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    nodes.value = await adminApi.adminSandboxStatus()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(load)

const onlineNodes = computed(() => nodes.value.filter((node) => node.status === 'online'))
const avgLoad = computed(() =>
  onlineNodes.value.length
    ? onlineNodes.value.reduce((sum, node) => sum + node.load, 0) / onlineNodes.value.length
    : 0,
)

function loadBarClass(load: number): string {
  if (load > 0.8) return TONE_SOLID_CLASSES.danger
  if (load > 0.5) return TONE_SOLID_CLASSES.warning
  return TONE_SOLID_CLASSES.success
}
</script>

<template>
  <WorkbenchShell :title="t('admin.sandbox.title')">
    <template #actions>
      <ToneBadge
        tone="success"
        :label="t('admin.sandbox.online', { online: onlineNodes.length, total: nodes.length })"
      />
      <ToneBadge
        tone="info"
        :label="t('admin.sandbox.avgLoad', { load: (avgLoad * 100).toFixed(0) })"
      />
      <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
    </template>

    <div class="min-h-0 flex-1 overflow-y-auto">
      <div v-if="loading && !nodes.length" class="grid min-h-[240px] place-items-center">
        <Loader2 class="size-6 animate-spin text-muted-foreground" />
      </div>

      <div v-else-if="nodes.length" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="node in nodes"
          :key="node.id"
          class="rounded-lg border border-border bg-card p-4"
        >
          <header class="flex items-center justify-between gap-2">
            <div class="flex min-w-0 items-center gap-2">
              <Server class="size-4 shrink-0 text-muted-foreground" :stroke-width="1.8" />
              <code class="truncate text-[12.5px] font-medium" :title="node.name">{{
                node.name
              }}</code>
            </div>
            <ToneBadge
              :tone="SANDBOX_STATUS[node.status]?.tag ?? 'info'"
              :label="SANDBOX_STATUS[node.status]?.label ?? node.status"
            />
          </header>

          <div class="mt-3.5 space-y-1.5">
            <div class="flex items-center justify-between text-[12px] text-muted-foreground">
              <span>{{ t('admin.sandbox.load') }}</span>
              <span class="tabular-nums">{{ Math.round(node.load * 100) }}%</span>
            </div>
            <div class="h-1.5 overflow-hidden rounded-full bg-muted">
              <div
                class="h-full rounded-full transition-[width] duration-300"
                :class="loadBarClass(node.load)"
                :style="{ width: `${Math.min(100, Math.round(node.load * 100))}%` }"
              />
            </div>
          </div>

          <dl class="mt-3 grid grid-cols-3 gap-2">
            <div class="rounded-md border border-border px-2 py-1.5">
              <dt class="flex items-center gap-1 text-[11px] text-muted-foreground">
                <Cpu class="size-3" :stroke-width="1.8" />
                CPU
              </dt>
              <dd class="mt-0.5 text-[12.5px] tabular-nums">{{ node.cpu_usage }}%</dd>
            </div>
            <div class="rounded-md border border-border px-2 py-1.5">
              <dt class="flex items-center gap-1 text-[11px] text-muted-foreground">
                <MemoryStick class="size-3" :stroke-width="1.8" />
                {{ t('admin.sandbox.memory') }}
              </dt>
              <dd class="mt-0.5 text-[12.5px] tabular-nums">{{ node.memory_usage }}%</dd>
            </div>
            <div class="rounded-md border border-border px-2 py-1.5">
              <dt class="flex items-center gap-1 text-[11px] text-muted-foreground">
                <Activity class="size-3" :stroke-width="1.8" />
                {{ t('admin.sandbox.tasks') }}
              </dt>
              <dd class="mt-0.5 text-[12.5px] tabular-nums">{{ node.running_tasks }}</dd>
            </div>
          </dl>

          <footer
            class="mt-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-t border-dashed border-border pt-2 text-[11px] text-muted-foreground"
          >
            <span class="truncate" :title="node.version">
              {{ t('admin.sandbox.version') }}: {{ node.version }}
            </span>
            <span class="tabular-nums">{{ formatDateTime(node.last_heartbeat_at) }}</span>
          </footer>
        </article>
      </div>

      <div v-else class="grid h-full min-h-[240px] place-items-center">
        <EmptyState :text="t('admin.sandbox.empty')" />
      </div>
    </div>
  </WorkbenchShell>
</template>
