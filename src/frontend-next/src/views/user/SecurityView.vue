<script setup lang="ts">
/**
 * 安全设置（/user/security）：修改密码 / 换绑邮箱（验证码 + 二次确认）/ 注销账号（密码确认）。
 * 注销为软注销：成功即清理本地会话并跳转登录页。
 */
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2, ShieldAlert } from '@lucide/vue'

import * as authApi from '@/api/auth'
import * as usersApi from '@/api/users'
import PasswordField from '@/components/auth/PasswordField.vue'
import EmailCodeInput from '@/components/common/EmailCodeInput.vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useUserStore } from '@/stores/user'
import { confirmDialog, message } from '@/utils/feedback'
import UserSettingsShell from './components/UserSettingsShell.vue'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const pwdForm = reactive({ old_password: '', new_password: '', confirm: '' })
const pwdLoading = ref(false)

const emailForm = reactive({ new_email: '', code: '' })
const emailLoading = ref(false)

const deactivateOpen = ref(false)
const deactivatePassword = ref('')
const deactivating = ref(false)

async function onChangePassword(): Promise<void> {
  if (!pwdForm.old_password || !pwdForm.new_password) {
    message.warning(t('security.fillPasswords'))
    return
  }
  if (pwdForm.new_password.length < 6) {
    message.warning(t('security.newPasswordShort'))
    return
  }
  if (pwdForm.new_password !== pwdForm.confirm) {
    message.warning(t('security.newPasswordMismatch'))
    return
  }
  pwdLoading.value = true
  try {
    await authApi.changePassword(pwdForm.old_password, pwdForm.new_password)
    message.success(t('security.passwordChanged'))
    Object.assign(pwdForm, { old_password: '', new_password: '', confirm: '' })
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('security.passwordChangeFailed'))
  } finally {
    pwdLoading.value = false
  }
}

async function onChangeEmail(): Promise<void> {
  emailLoading.value = true
  try {
    await authApi.changeEmail(emailForm.new_email, emailForm.code)
    message.success(t('security.emailChanged'))
    Object.assign(emailForm, { new_email: '', code: '' })
    // 换绑后刷新当前用户，个人资料页与壳层展示的邮箱立即同步
    try {
      userStore.$patch({ user: await usersApi.getMe() })
    } catch {
      /* 刷新失败不阻断换绑结果提示 */
    }
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('security.emailChangeFailed'))
  } finally {
    emailLoading.value = false
  }
}

/** 换绑邮箱前的二次确认（关键操作需确认） */
async function requestChangeEmail(): Promise<void> {
  if (!emailForm.new_email || !emailForm.code) {
    message.warning(t('security.enterEmailCode'))
    return
  }
  const ok = await confirmDialog({
    title: t('security.confirmEmailChange'),
    content: `${t('security.newEmail')}: ${emailForm.new_email}`,
    positiveText: t('security.confirmEmailChange'),
    negativeText: t('action.cancel'),
  })
  if (!ok) return
  await onChangeEmail()
}

function openDeactivate(): void {
  deactivatePassword.value = ''
  deactivateOpen.value = true
}

async function confirmDeactivate(): Promise<void> {
  if (!deactivatePassword.value) {
    message.warning(t('auth.password'))
    return
  }
  deactivating.value = true
  try {
    await userStore.deactivate(deactivatePassword.value)
    message.success(t('security.deactivated'))
    deactivateOpen.value = false
    void router.push('/login')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    deactivating.value = false
  }
}
</script>

<template>
  <UserSettingsShell>
    <div class="space-y-4">
      <div class="grid gap-4 md:grid-cols-2 md:items-start">
        <Card>
          <header class="border-b border-border px-5 py-3.5">
            <h2 class="text-[14px] font-semibold">{{ t('security.changePassword') }}</h2>
          </header>
          <form class="space-y-4 px-5 py-4" @submit.prevent="onChangePassword">
            <div class="grid gap-1.5">
              <Label class="text-[12.5px]">{{ t('security.oldPassword') }}</Label>
              <PasswordField v-model="pwdForm.old_password" autocomplete="current-password" />
            </div>
            <div class="grid gap-1.5">
              <Label class="text-[12.5px]">{{ t('security.newPassword') }}</Label>
              <PasswordField v-model="pwdForm.new_password" autocomplete="new-password" />
            </div>
            <div class="grid gap-1.5">
              <Label class="text-[12.5px]">{{ t('security.confirmNewPassword') }}</Label>
              <PasswordField v-model="pwdForm.confirm" autocomplete="new-password" />
            </div>
            <Button type="submit" size="toolbar" :disabled="pwdLoading">
              <Loader2 v-if="pwdLoading" class="size-3.5 animate-spin" />
              {{ t('security.changePassword') }}
            </Button>
          </form>
        </Card>

        <Card>
          <header class="border-b border-border px-5 py-3.5">
            <h2 class="text-[14px] font-semibold">{{ t('security.changeEmail') }}</h2>
          </header>
          <form class="space-y-4 px-5 py-4" @submit.prevent="requestChangeEmail">
            <div class="grid gap-1.5">
              <Label for="security-new-email" class="text-[12.5px]">
                {{ t('security.newEmail') }}
              </Label>
              <Input
                id="security-new-email"
                v-model="emailForm.new_email"
                type="email"
                autocomplete="email"
                placeholder="you@example.com"
                class="h-9 text-[13px]"
              />
            </div>
            <div class="grid gap-1.5">
              <Label class="text-[12.5px]">{{ t('auth.code') }}</Label>
              <EmailCodeInput
                v-model:code="emailForm.code"
                :email="emailForm.new_email"
                action="change_email"
                @enter="requestChangeEmail"
              />
            </div>
            <Button type="submit" size="toolbar" :disabled="emailLoading">
              <Loader2 v-if="emailLoading" class="size-3.5 animate-spin" />
              {{ t('security.confirmEmailChange') }}
            </Button>
          </form>
        </Card>
      </div>

      <section class="rounded-xl border border-destructive/35 bg-destructive/[0.04]">
        <header class="flex items-center gap-2 border-b border-destructive/25 px-5 py-3.5">
          <ShieldAlert class="size-4 text-destructive" :stroke-width="1.8" />
          <h2 class="text-[14px] font-semibold text-destructive">{{ t('security.danger') }}</h2>
        </header>
        <div class="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div class="min-w-0">
            <p class="text-[13.5px] font-medium">{{ t('security.deactivate') }}</p>
            <p class="mt-1 max-w-[70ch] text-[12px] leading-5 text-muted-foreground">
              {{ t('security.deactivateDescription') }}
            </p>
          </div>
          <Button variant="destructive" size="toolbar" @click="openDeactivate">
            {{ t('security.deactivate') }}
          </Button>
        </div>
      </section>
    </div>

    <Dialog v-model:open="deactivateOpen">
      <DialogContent class="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle class="text-[15px]">{{ t('security.deactivateTitle') }}</DialogTitle>
          <DialogDescription class="text-[12.5px] leading-5">
            {{ t('security.deactivatePrompt') }}
          </DialogDescription>
        </DialogHeader>
        <PasswordField v-model="deactivatePassword" autocomplete="current-password" />
        <DialogFooter class="gap-2">
          <Button
            variant="outline"
            size="sm"
            :disabled="deactivating"
            @click="deactivateOpen = false"
          >
            {{ t('action.cancel') }}
          </Button>
          <Button
            variant="destructive"
            size="sm"
            :disabled="deactivating"
            @click="confirmDeactivate"
          >
            <Loader2 v-if="deactivating" class="size-3.5 animate-spin" />
            {{ t('security.deactivateConfirm') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </UserSettingsShell>
</template>
