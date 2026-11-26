<script setup lang="ts">
import { onMounted, watch } from 'vue'

import ConfirmDialogHost from '@/components/feedback/ConfirmDialogHost.vue'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { refreshDocumentTitle } from '@/router'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

onMounted(() => {
  appStore.loadSiteConfig()
})

watch(
  () => appStore.siteConfig.name,
  () => refreshDocumentTitle(),
)
</script>

<template>
  <TooltipProvider :ignore-non-keyboard-focus="true">
    <div class="min-h-dvh bg-background text-foreground">
      <router-view />
    </div>
  </TooltipProvider>
  <Toaster position="top-center" :duration="3200" :theme="appStore.isDark ? 'dark' : 'light'" />
  <ConfirmDialogHost />
</template>
