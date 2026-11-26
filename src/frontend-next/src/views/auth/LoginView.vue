<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import AuthLayout from '@/components/auth/AuthLayout.vue'
import PasswordField from '@/components/auth/PasswordField.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const { t } = useI18n()

const form = reactive({ email: '', password: '' })
const loading = ref(false)

async function onSubmit(): Promise<void> {
  if (!form.email || !form.password) {
    message.warning(t('auth.enterEmailPassword'))
    return
  }
  loading.value = true
  try {
    await userStore.login(form.email, form.password)
    message.success(t('auth.loginSuccess'))
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    router.push(redirect || '/')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('auth.loginFailed'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthLayout :title="t('user.login')" :subtitle="t('home.intro')">
    <form class="mt-8 grid gap-5" @submit.prevent="onSubmit">
      <div class="grid gap-2">
        <Label for="login-email" class="text-[13px] font-medium">{{ t('auth.email') }}</Label>
        <Input
          id="login-email"
          v-model="form.email"
          type="email"
          autocomplete="username"
          placeholder="you@example.com"
          class="h-10 text-[13.5px]"
        />
      </div>

      <div class="grid gap-2">
        <Label for="login-password" class="text-[13px] font-medium">{{ t('auth.password') }}</Label>
        <PasswordField v-model="form.password" autocomplete="current-password" />
      </div>

      <Button type="submit" class="mt-1 h-10 w-full" :disabled="loading">
        <Loader2 v-if="loading" class="size-4 animate-spin" />
        <span>{{ t('user.login') }}</span>
      </Button>
    </form>

    <p class="mt-7 text-[13px] text-muted-foreground">
      {{ t('auth.noAccount') }}
      <button
        type="button"
        class="font-medium text-foreground underline-offset-4 hover:underline"
        @click="router.push('/register')"
      >
        {{ t('auth.registerNow') }}
      </button>
    </p>
  </AuthLayout>
</template>
