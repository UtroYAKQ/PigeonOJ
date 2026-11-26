<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { Toaster } from 'vue-sonner'

import ConfirmDialogHost from '@/components/feedback/ConfirmDialogHost.vue'
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
  <Toaster
    position="top-center"
    :duration="3200"
    :theme="appStore.isDark ? 'dark' : 'light'"
    :toast-options="{
      style: {
        background: 'var(--popover)',
        color: 'var(--popover-foreground)',
        border: '1px solid var(--border)',
        boxShadow: 'none',
        fontFamily: 'var(--font-sans)',
        fontSize: '13.5px',
        borderRadius: '10px',
      },
    }"
  />
  <ConfirmDialogHost />
</template>
