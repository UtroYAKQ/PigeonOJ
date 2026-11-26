<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Code2 } from '@lucide/vue'

import EntityCard from '@/components/common/EntityCard.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import { languageOptions } from '@/constants/languages'
import { formatDateTime } from '@/utils/format'
import type { CodeShareLanguage, CodeShareSummary } from '@/types'

defineProps<{ share: CodeShareSummary }>()

const emit = defineEmits<{ open: [share: CodeShareSummary] }>()

const { t } = useI18n()

function languageLabel(value: CodeShareLanguage): string {
  return languageOptions.find((item) => item.value === value)?.label ?? value
}
</script>

<template>
  <EntityCard @select="emit('open', share)">
    <div class="flex items-start gap-3">
      <span
        class="grid size-10 shrink-0 place-items-center rounded-lg bg-surface text-muted-foreground"
        aria-hidden="true"
      >
        <Code2 class="size-[18px]" :stroke-width="1.8" />
      </span>
      <div class="min-w-0 flex-1">
        <div class="flex items-start gap-2">
          <h3 class="line-clamp-1 min-w-0 flex-1 text-sm font-semibold leading-5">
            {{ share.title }}
          </h3>
          <ToneBadge
            v-if="share.status === 'removed'"
            tone="default"
            :label="t('codes.statusRemoved')"
          />
        </div>
        <p class="mt-1.5 line-clamp-2 min-h-[2.5rem] text-[13px] leading-5 text-muted-foreground">
          {{ share.description_excerpt || t('codes.noExcerpt') }}
        </p>
      </div>
    </div>

    <div
      class="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 pt-3 text-xs text-muted-foreground"
    >
      <span class="font-mono">{{ languageLabel(share.language) }}</span>
      <span class="truncate">{{ share.author.nickname }}</span>
      <span class="tabular-nums">{{ formatDateTime(share.updated_at) }}</span>
    </div>
  </EntityCard>
</template>
