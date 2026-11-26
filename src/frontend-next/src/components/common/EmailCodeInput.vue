<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useIntervalFn } from '@vueuse/core'

import * as authApi from '@/api/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { message } from '@/utils/feedback'

const props = defineProps<{
  email: string
  action: string
}>()

const code = defineModel<string>('code', { default: '' })
const emit = defineEmits<{ enter: [] }>()

const { t } = useI18n()
const sending = ref(false)
const countdown = ref(0)

const { pause, resume } = useIntervalFn(
  () => {
    countdown.value -= 1
    if (countdown.value <= 0) pause()
  },
  1000,
  { immediate: false },
)

async function send(): Promise<void> {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(props.email)) {
    message.warning(t('auth.validEmail'))
    return
  }
  sending.value = true
  try {
    const result = await authApi.sendEmailCode(props.email, props.action)
    if (result?.hint) message.info(result.hint)
    else message.success(t('auth.codeSent'))
    countdown.value = 60
    resume()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('auth.sendFailed'))
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <div class="flex w-full gap-2.5">
    <Input
      v-model="code"
      maxlength="6"
      inputmode="numeric"
      :placeholder="t('auth.code')"
      class="h-9 flex-1 font-mono tracking-[0.25em]"
      @keyup.enter="emit('enter')"
    />
    <Button
      variant="outline"
      :disabled="countdown > 0 || sending"
      class="h-9 shrink-0 text-[13px]"
      @click="send"
    >
      {{ countdown > 0 ? t('auth.resend', { seconds: countdown }) : t('auth.getCode') }}
    </Button>
  </div>
</template>
