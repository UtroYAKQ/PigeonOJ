<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Loader2, Snowflake } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import ContestToolCard from './ContestToolCard.vue'

defineProps<{
  canUnfreeze: boolean
  unfreezing: boolean
  disabledHint: string
}>()

defineEmits<{ unfreeze: [] }>()

const { t } = useI18n()
</script>

<template>
  <ContestToolCard :title="t('contests.tools.boardOps')" :hint="t('contests.tools.unfreezeHint')">
    <Button
      variant="outline"
      size="sm"
      class="self-start"
      :disabled="!canUnfreeze || unfreezing"
      @click="$emit('unfreeze')"
    >
      <Loader2 v-if="unfreezing" class="size-3.5 animate-spin" />
      <Snowflake v-else class="size-3.5" />
      {{ t('contests.detail.unfreeze') }}
    </Button>
    <p v-if="!canUnfreeze" class="text-[12px] text-muted-foreground">{{ disabledHint }}</p>
  </ContestToolCard>
</template>
