<script setup lang="ts">
/**
 * 邮箱验证码输入行：验证码输入框 + 发送按钮（60s 倒计时内聚）。
 * 注册页与安全设置换绑邮箱共用；发送前校验邮箱格式，业务提示由本组件统一给出。
 */
import { onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import * as authApi from '@/api/auth'
import { message } from '@/utils/feedback'

const props = withDefaults(
  defineProps<{
    /** 目标邮箱：发送前按格式校验 */
    email: string
    /** 验证码用途（透传 sendEmailCode purpose） */
    action: string
    /** 控件尺寸，跟随所在表单 */
    size?: 'small' | 'medium' | 'large'
  }>(),
  { size: 'medium' },
)

const code = defineModel<string>('code', { default: '' })
const emit = defineEmits<{ enter: [] }>()

const { t } = useI18n()
const sending = ref(false)
const countdown = ref(0)
let timer: ReturnType<typeof setInterval> | null = null

function startCountdown() {
  countdown.value = 60
  timer = setInterval(() => {
    if (--countdown.value <= 0 && timer) {
      clearInterval(timer)
      timer = null
    }
  }, 1000)
}
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})

async function send() {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(props.email)) {
    message.warning(t('auth.validEmail'))
    return
  }
  sending.value = true
  try {
    const res = await authApi.sendEmailCode(props.email, props.action)
    if (res?.hint) message.info(res.hint)
    else message.success(t('auth.codeSent'))
    startCountdown()
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('auth.sendFailed'))
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <div class="email-code">
    <n-input
      v-model:value="code"
      :size="size"
      maxlength="6"
      :placeholder="t('auth.code')"
      @keyup.enter="emit('enter')"
    />
    <n-button :size="size" :disabled="countdown > 0" :loading="sending" @click="send">
      {{ countdown > 0 ? t('auth.resend', { seconds: countdown }) : t('auth.getCode') }}
    </n-button>
  </div>
</template>

<style scoped>
.email-code {
  display: flex;
  gap: 10px;
  width: 100%;
}
.email-code > :first-child {
  flex: 1;
}
</style>
