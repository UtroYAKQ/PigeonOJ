<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { MonitorPlay } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import ContestToolCard from './ContestToolCard.vue'

defineProps<{ canScrollboard: boolean }>()

defineEmits<{ open: [] }>()

const { t } = useI18n()
</script>

<template>
  <ContestToolCard
    :title="t('contests.tools.scrollboard')"
    :hint="t('contests.tools.scrollboardHint')"
  >
    <Button
      variant="outline"
      size="sm"
      class="self-start"
      :disabled="!canScrollboard"
      @click="$emit('open')"
    >
      <MonitorPlay class="size-3.5" />
      {{ t('contests.tools.scrollboardOpen') }}
    </Button>
    <p v-if="!canScrollboard" class="text-[12px] text-muted-foreground">
      {{ t('contests.tools.scrollboardDisabled') }}
    </p>
  </ContestToolCard>
</template>
