<script setup lang="ts">
import { useI18n } from 'vue-i18n'

defineProps<{
  loading?: boolean
  confirmText?: string
}>()

defineEmits<{
  cancel: []
  confirm: []
}>()

const { t } = useI18n()
</script>

<template>
  <div class="modal-footer">
    <n-button @click="$emit('cancel')">{{ t('action.cancel') }}</n-button>
    <n-button type="primary" :loading="loading" @click="$emit('confirm')">
      {{ confirmText ?? t('action.confirm') }}
    </n-button>
  </div>
</template>

<style scoped>
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
