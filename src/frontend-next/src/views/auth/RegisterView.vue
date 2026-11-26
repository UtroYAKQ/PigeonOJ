<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2, TriangleAlert } from '@lucide/vue'

import * as authApi from '@/api/auth'
import AuthLayout from '@/components/auth/AuthLayout.vue'
import PasswordField from '@/components/auth/PasswordField.vue'
import EmailCodeInput from '@/components/common/EmailCodeInput.vue'
import InlineNotice from '@/components/common/InlineNotice.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAppStore } from '@/stores/app'
import { message } from '@/utils/feedback'

const router = useRouter()
const { t } = useI18n()
const appStore = useAppStore()

const registrationClosed = computed(() => !appStore.siteConfig.register_enabled)
const emailVerifyEnabled = computed(() => appStore.siteConfig.email_verify_enabled)

const form = reactive({ email: '', nickname: '', code: '', password: '', confirm: '' })
const loading = ref(false)

async function onSubmit(): Promise<void> {
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
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('auth.registerFailed'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthLayout
    :title="t('auth.registerTitle', { name: appStore.siteName })"
    :subtitle="t('home.intro')"
  >
    <InlineNotice v-if="registrationClosed" tone="warning" :icon="TriangleAlert" class="mt-6">
      {{ t('auth.registerDisabled') }}
    </InlineNotice>

    <form v-else class="mt-8 grid gap-4" @submit.prevent="onSubmit">
      <div class="grid gap-2">
        <Label for="register-email" class="text-[13px] font-medium">{{ t('auth.email') }}</Label>
        <Input
          id="register-email"
          v-model="form.email"
          type="email"
          autocomplete="email"
          placeholder="you@example.com"
          class="h-10 text-[13.5px]"
        />
      </div>

      <div class="grid gap-2">
        <Label for="register-nickname" class="text-[13px] font-medium">{{
          t('auth.nickname')
        }}</Label>
        <Input
          id="register-nickname"
          v-model="form.nickname"
          maxlength="64"
          :placeholder="t('auth.nicknamePlaceholder')"
          class="h-10 text-[13.5px]"
        />
      </div>

      <div v-if="emailVerifyEnabled" class="grid gap-2">
        <Label class="text-[13px] font-medium">{{ t('auth.code') }}</Label>
        <EmailCodeInput
          v-model:code="form.code"
          :email="form.email"
          action="register"
          @enter="onSubmit"
        />
      </div>

      <div class="grid gap-2">
        <Label for="register-password" class="text-[13px] font-medium">{{
          t('auth.password')
        }}</Label>
        <PasswordField v-model="form.password" autocomplete="new-password" />
      </div>

      <div class="grid gap-2">
        <Label for="register-confirm" class="text-[13px] font-medium">
          {{ t('auth.confirmPassword') }}
        </Label>
        <PasswordField v-model="form.confirm" autocomplete="new-password" />
      </div>

      <Button type="submit" class="mt-1 h-10 w-full" :disabled="loading">
        <Loader2 v-if="loading" class="size-4 animate-spin" />
        <span>{{ t('user.register') }}</span>
      </Button>
    </form>

    <p class="mt-6 text-[13px] text-muted-foreground">
      {{ t('auth.hasAccount') }}
      <button
        type="button"
        class="font-medium text-foreground underline-offset-4 hover:underline"
        @click="router.push('/login')"
      >
        {{ t('auth.backLogin') }}
      </button>
    </p>
  </AuthLayout>
</template>
