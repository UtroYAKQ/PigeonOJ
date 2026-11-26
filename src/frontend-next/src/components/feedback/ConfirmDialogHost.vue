<script setup lang="ts">
import { computed } from 'vue'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { closeConfirm, confirmState } from '@/utils/feedback'

const options = computed(() => confirmState.options)

function onOpenChange(open: boolean): void {
  if (!open) closeConfirm(false)
}
</script>

<template>
  <Dialog :open="confirmState.open" @update:open="onOpenChange">
    <DialogContent class="sm:max-w-[420px]">
      <DialogHeader>
        <DialogTitle>{{ options?.title }}</DialogTitle>
        <DialogDescription v-if="options?.content" class="whitespace-pre-line">
          {{ options.content }}
        </DialogDescription>
      </DialogHeader>
      <DialogFooter class="gap-2">
        <Button variant="outline" @click="closeConfirm(false)">
          {{ options?.negativeText ?? 'Cancel' }}
        </Button>
        <Button :variant="options?.danger ? 'destructive' : 'default'" @click="closeConfirm(true)">
          {{ options?.positiveText ?? 'Confirm' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
