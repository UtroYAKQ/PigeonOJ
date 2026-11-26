<script setup lang="ts">
import { computed } from 'vue'

import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { closeConfirm, confirmState } from '@/utils/feedback'

const options = computed(() => confirmState.options)

function onOpenChange(open: boolean): void {
  if (!open) closeConfirm(false)
}
</script>

<template>
  <AlertDialog :open="confirmState.open" @update:open="onOpenChange">
    <AlertDialogContent size="sm">
      <AlertDialogHeader>
        <AlertDialogTitle>{{ options?.title }}</AlertDialogTitle>
        <AlertDialogDescription v-if="options?.content" class="whitespace-pre-line">
          {{ options.content }}
        </AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter class="gap-2">
        <Button variant="outline" @click="closeConfirm(false)">
          {{ options?.negativeText ?? 'Cancel' }}
        </Button>
        <Button :variant="options?.danger ? 'destructive' : 'default'" @click="closeConfirm(true)">
          {{ options?.positiveText ?? 'Confirm' }}
        </Button>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
</template>