<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { adminSetRole } from '@/api/admin'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ROLE_NAME } from '@/constants/dict'
import { message } from '@/utils/feedback'
import type { GlobalRoleCode, User } from '@/types'

const props = defineProps<{
  open: boolean
  user: User | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  saved: []
}>()

const { t } = useI18n()
const roleId = ref<GlobalRoleCode | ''>('')
const saving = ref(false)

const roleOptions = computed(() =>
  (Object.keys(ROLE_NAME) as GlobalRoleCode[]).map((code) => ({ code, label: ROLE_NAME[code] })),
)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    roleId.value = props.user?.roles?.[0] ?? ''
  },
)

function close(): void {
  emit('update:open', false)
}

async function save(): Promise<void> {
  if (!props.user || saving.value) return
  if (!roleId.value) {
    message.warning(t('admin.users.pickRole'))
    return
  }
  saving.value = true
  try {
    await adminSetRole(props.user.id, roleId.value)
    message.success(t('admin.users.rolesUpdated'))
    close()
    emit('saved')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.updateFailed'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="sm:max-w-[420px]">
      <DialogHeader>
        <DialogTitle class="text-[15px] font-semibold">
          {{ t('admin.users.roleTitle', { name: user?.nickname ?? '' }) }}
        </DialogTitle>
        <DialogDescription class="sr-only">{{ t('admin.users.role') }}</DialogDescription>
      </DialogHeader>

      <div class="grid gap-2" role="radiogroup" :aria-label="t('admin.users.role')">
        <label
          v-for="option in roleOptions"
          :key="option.code"
          class="flex cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2.5 text-[13px] transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring/50"
          :class="
            roleId === option.code
              ? 'border-foreground/25 bg-muted'
              : 'border-border hover:bg-muted/50'
          "
        >
          <input
            v-model="roleId"
            type="radio"
            name="admin-user-role"
            :value="option.code"
            class="sr-only"
          />
          <span
            class="grid size-3.5 shrink-0 place-items-center rounded-full border"
            :class="roleId === option.code ? 'border-foreground' : 'border-muted-foreground/50'"
          >
            <span v-if="roleId === option.code" class="size-1.5 rounded-full bg-foreground" />
          </span>
          <span>{{ option.label }}</span>
        </label>
      </div>

      <DialogFooter>
        <Button variant="outline" size="sm" :disabled="saving" @click="close">
          {{ t('action.cancel') }}
        </Button>
        <Button size="sm" :disabled="saving" @click="save">
          <Loader2 v-if="saving" class="size-4 animate-spin" />
          {{ t('action.save') }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
