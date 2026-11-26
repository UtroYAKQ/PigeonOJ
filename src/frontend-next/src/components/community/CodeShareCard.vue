<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import BaseAvatar from '@/components/common/BaseAvatar.vue'
import EntityCard from '@/components/common/EntityCard.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import { languageOptions } from '@/constants/languages'
import { formatDate } from '@/utils/format'
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
      <BaseAvatar
        kind="user"
        :src="share.author.avatar_url"
        :name="share.author.nickname"
        :size="36"
      />
      <div class="min-w-0 flex-1">
        <div class="flex min-w-0 items-center gap-2">
          <h3
            :title="share.title"
            class="min-w-0 flex-1 truncate text-[14px] font-semibold leading-5"
          >
            {{ share.title }}
          </h3>
          <ToneBadge
            v-if="share.status === 'removed'"
            tone="default"
            :label="t('codes.statusRemoved')"
            class="shrink-0"
          />
        </div>
        <p class="mt-1 line-clamp-1 min-h-5 text-[12.5px] leading-5 text-muted-foreground">
          {{ share.description_excerpt || t('codes.noExcerpt') }}
        </p>
      </div>
    </div>

    <div
      class="mt-3 flex min-w-0 items-center gap-2 text-[12px] text-muted-foreground"
    >
      <span class="shrink-0 font-mono text-[11.5px]">{{ languageLabel(share.language) }}</span>
      <span aria-hidden="true" class="text-muted-foreground/40">·</span>
      <span class="truncate">{{ share.author.nickname }}</span>
    </div>

    <div
      class="mt-auto flex items-center border-t border-border pt-2.5 text-[11px] tabular-nums text-muted-foreground"
    >
      <span class="truncate">
        {{ t('common.updatedAtValue', { time: formatDate(share.updated_at) }) }}
      </span>
    </div>
  </EntityCard>
</template>