<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Moon, Sun } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import { TooltipHint } from '@/components/ui/tooltip'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
const { t } = useI18n()

const tip = computed(() => (appStore.isDark ? t('profile.light') : t('profile.dark')))
</script>

<template>
  <TooltipHint :text="tip">
    <Button
      variant="ghost"
      size="icon-sm"
      :aria-label="t('profile.theme')"
      @click="appStore.toggleTheme()"
    >
      <Sun v-if="appStore.isDark" class="size-4" />
      <Moon v-else class="size-4" />
    </Button>
  </TooltipHint>
</template>
