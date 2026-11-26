<script setup lang="ts">
/**
 * 系统配置行：配置键 / 说明 / 修改人 / 更新时间 / 值摘要 + 编辑入口。
 * 值摘要与编辑器口径统一收敛在 config-meta.ts。
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Pencil } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/utils/format'
import type { SystemConfigItem } from '@/types'
import { describeConfigValue } from './config-meta'

const props = defineProps<{ item: SystemConfigItem }>()
const emit = defineEmits<{ edit: [] }>()

const { t } = useI18n()
const summary = computed(() => describeConfigValue(props.item))
</script>

<template>
  <div class="flex flex-wrap items-start gap-x-6 gap-y-2 py-4 transition-colors hover:bg-muted/20">
    <div class="min-w-0 flex-1 basis-[260px]">
      <code class="break-all text-sm font-medium">{{ item.config_key }}</code>
      <p v-if="item.description" class="mt-1 text-[13px] leading-5 text-muted-foreground">
        {{ item.description }}
      </p>
      <p class="mt-1 flex flex-wrap items-center gap-x-3 text-[12px] text-muted-foreground/80">
        <span>{{ t('config.updater') }}: {{ item.updated_by ?? '—' }}</span>
        <span>{{ t('config.updatedAt') }}: {{ formatDateTime(item.updated_at) }}</span>
      </p>
    </div>

    <p
      class="min-w-0 flex-1 basis-[220px] break-words text-sm leading-6 text-muted-foreground"
      :title="summary"
    >
      {{ summary }}
    </p>

    <Button variant="ghost" size="sm" class="shrink-0" @click="emit('edit')">
      <Pencil class="size-4" />
      {{ t('action.edit') }}
    </Button>
  </div>
</template>
