<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RefreshCw } from '@lucide/vue'

import { Button } from '@/components/ui/button'

withDefaults(defineProps<{ message: string; retryLabel?: string }>(), { retryLabel: undefined })

const emit = defineEmits<{ retry: [] }>()
const { t } = useI18n()
</script>

<template>
  <div class="flex flex-col items-center gap-3 px-6 text-center">
    <p class="text-[13px] text-muted-foreground">{{ message }}</p>
    <div class="flex flex-wrap items-center justify-center gap-2">
      <slot name="actions">
        <Button variant="outline" size="sm" @click="emit('retry')">
          <RefreshCw class="size-3.5" />
          {{ retryLabel ?? t('action.refresh') }}
        </Button>
      </slot>
    </div>
  </div>
</template>