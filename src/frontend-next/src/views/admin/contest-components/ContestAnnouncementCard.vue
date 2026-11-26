<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import MarkdownEditor from '@/components/common/MarkdownEditor.vue'
import MarkdownView from '@/components/common/MarkdownView.vue'
import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/utils/format'
import type { ContestStatusType } from '@/types'
import ContestToolCard from './ContestToolCard.vue'

const props = defineProps<{
  modelValue: string
  status: ContestStatusType
  saving?: boolean
  dirty?: boolean
  updatedAt?: string | null
}>()

defineEmits<{
  'update:modelValue': [value: string]
  save: []
}>()

const { t } = useI18n()

const hint = computed(() =>
  props.status === 'scheduled'
    ? t('contests.tools.announcementPrepare')
    : t('contests.tools.announcementHint'),
)
</script>

<template>
  <ContestToolCard :title="t('contests.tools.announcement')" :hint="hint">
    <MarkdownEditor
      :model-value="modelValue"
      compact
      min-height="240px"
      :placeholder="t('contests.tools.announcementPlaceholder')"
      @update:model-value="$emit('update:modelValue', $event)"
    />

    <div class="flex flex-wrap items-center gap-2">
      <Button size="sm" :disabled="!dirty || saving" @click="$emit('save')">
        <Loader2 v-if="saving" class="size-3.5 animate-spin" />
        {{ t('action.save') }}
      </Button>
      <span v-if="updatedAt" class="text-[12px] text-muted-foreground">
        {{ t('contests.detail.announcementUpdatedAt') }} {{ formatDateTime(updatedAt) }}
      </span>
    </div>

    <div v-if="modelValue.trim()" class="rounded-lg border border-dashed border-border p-3">
      <p class="mb-1.5 text-[12px] font-medium text-muted-foreground">
        {{ t('contests.tools.preview') }}
      </p>
      <MarkdownView :source="modelValue" />
    </div>
  </ContestToolCard>
</template>
