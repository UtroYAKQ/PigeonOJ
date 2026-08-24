<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import * as authApi from '@/api/auth'
import { useAppStore } from '@/stores/app'
import { message } from '@/utils/feedback'

const router = useRouter()
const { t } = useI18n()
const appStore = useAppStore()
const registrationClosed = computed(() => !appStore.siteConfig.register_enabled)
const emailVerifyEnabled = computed(() => appStore.siteConfig.email_verify_enabled)
const siteName = computed(() => appStore.siteConfig.name || 'PigeonOJ')
const form = reactive({ email: '', nickname: '', code: '', password: '', confirm: '' })
const loading = ref(false)
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
async function onSendCode() {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    message.warning(t('auth.validEmail'))
    return
  }
  sending.value = true
  try {
    const res = await authApi.sendEmailCode(form.email, 'register')
    if (res?.hint) message.info(res.hint)
    else message.success(t('auth.codeSent'))
    startCountdown()
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('auth.sendFailed'))
  } finally {
    sending.value = false
  }
}
async function onSubmit() {
  if (registrationClosed.value) return
  if (!form.email || !form.nickname || (emailVerifyEnabled.value && !form.code) || !form.password) {
    message.warning(t('auth.completeRegistration'))
    return
  }
  if (form.password.length < 6) {
    message.warning(t('auth.passwordTooShort'))
    return
  }
  if (form.password !== form.confirm) {
    message.warning(t('auth.passwordMismatch'))
    return
  }
  loading.value = true
  try {
    await authApi.register({
      email: form.email,
      code: form.code,
      password: form.password,
      nickname: form.nickname,
    })
    message.success(t('auth.registerSuccess'))
    router.push('/login')
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('auth.registerFailed'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="register-page">
    <header class="register-page__brand" @click="router.push('/')">
      <span>🐦</span><strong>{{ siteName }}</strong>
    </header>
    <main class="register-pane">
      <n-card class="register-card" :bordered="false">
        <div class="register-card__heading">
          <p>{{ t('app.tagline') }}</p>
          <h1>{{ t('auth.registerTitle') }}</h1>
          <span>{{ t('home.intro') }}</span>
        </div>
        <n-alert v-if="registrationClosed" type="warning" class="register-card__closed">
          {{ t('auth.registerDisabled') }}
        </n-alert>
        <n-form v-else label-placement="top" @submit.prevent="onSubmit">
          <n-form-item :label="t('auth.email')">
            <n-input
              v-model:value="form.email"
              size="large"
              placeholder="you@example.com"
              autocomplete="email"
            />
          </n-form-item>
          <n-form-item :label="t('auth.nickname')">
            <n-input
              v-model:value="form.nickname"
              size="large"
              maxlength="64"
              :placeholder="t('auth.nicknamePlaceholder')"
            />
          </n-form-item>
          <n-form-item v-if="emailVerifyEnabled" :label="t('auth.code')">
            <div class="code-row">
              <n-input
                v-model:value="form.code"
                size="large"
                maxlength="6"
                :placeholder="t('auth.code')"
                @keyup.enter="onSubmit"
              />
              <n-button
                size="large"
                :disabled="countdown > 0"
                :loading="sending"
                @click="onSendCode"
              >
                {{ countdown > 0 ? t('auth.resend', { seconds: countdown }) : t('auth.getCode') }}
              </n-button>
            </div>
          </n-form-item>
          <n-form-item :label="t('auth.password')">
            <n-input
              v-model:value="form.password"
              type="password"
              show-password-on="click"
              size="large"
              :placeholder="t('auth.passwordMin')"
              autocomplete="new-password"
            />
          </n-form-item>
          <n-form-item :label="t('auth.confirmPassword')">
            <n-input
              v-model:value="form.confirm"
              type="password"
              show-password-on="click"
              size="large"
              :placeholder="t('auth.repeatPassword')"
              @keyup.enter="onSubmit"
            />
          </n-form-item>
          <n-button type="primary" size="large" block :loading="loading" attr-type="submit">
            {{ t('user.register') }}
          </n-button>
        </n-form>
        <p class="register-card__footer">
          {{ t('auth.hasAccount') }}
          <n-button text type="primary" @click="router.push('/login')">{{
            t('auth.backLogin')
          }}</n-button>
        </p>
      </n-card>
    </main>
  </div>
</template>

<style scoped>
.register-page {
  min-height: 100dvh;
  padding: 24px;
  background: var(--app-content-bg);
}
.register-page__brand {
  display: flex;
  align-items: center;
  gap: 9px;
  width: max-content;
  color: var(--app-text);
  cursor: pointer;
  font-size: 17px;
}
.register-page__brand span {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  background: #ffffff;
}
.register-card {
  width: min(100%, 480px);
  margin: clamp(20px, 6vh, 56px) auto 40px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.register-card__closed {
  margin-bottom: 16px;
}
.register-card__heading p {
  margin: 0 0 8px;
  color: var(--app-text-secondary);
  font-size: 13px;
}
.register-card__heading h1 {
  margin: 0;
  font-size: 22px;
}
.register-card__heading span {
  display: block;
  margin: 10px 0 20px;
  color: var(--app-text-secondary);
  font-size: 13px;
  line-height: 1.65;
}
.register-card__footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin: 16px 0 0;
  color: var(--app-text-secondary);
  font-size: 13px;
}
.code-row {
  display: flex;
  gap: 10px;
  width: 100%;
}
.code-row > :first-child {
  flex: 1;
}
@media (max-width: 560px) {
  .register-page {
    padding: 16px;
  }
}
</style>
