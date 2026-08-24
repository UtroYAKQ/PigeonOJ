<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import * as authApi from '@/api/auth'
import { useUserStore } from '@/stores/user'
import { dialog, message } from '@/utils/feedback'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()
const pwdForm = reactive({ old_password: '', new_password: '', confirm: '' })
const pwdLoading = ref(false)
const emailForm = reactive({ new_email: '', code: '' })
const emailLoading = ref(false)
const sending = ref(false)
const countdown = ref(0)
/** 注销确认弹窗：需要输入登录密码（替代原 prompt 弹窗） */
const deactivateVisible = ref(false)
const deactivatePassword = ref('')
const deactivating = ref(false)
let timer: ReturnType<typeof setInterval> | null = null
async function onChangePassword() {
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
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('security.passwordChangeFailed'))
  } finally {
    pwdLoading.value = false
  }
}
function startCountdown() {
  countdown.value = 60
  timer = setInterval(() => {
    if (--countdown.value <= 0 && timer) {
      clearInterval(timer)
      timer = null
    }
  }, 1000)
}
async function onSendEmailCode() {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailForm.new_email)) {
    message.warning(t('auth.validEmail'))
    return
  }
  sending.value = true
  try {
    const res = await authApi.sendEmailCode(emailForm.new_email, 'change_email')
    if (res?.hint) message.info(res.hint)
    else message.success(t('auth.codeSent'))
    startCountdown()
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('security.sendCodeFailed'))
  } finally {
    sending.value = false
  }
}
async function onChangeEmail() {
  if (!emailForm.new_email || !emailForm.code) {
    message.warning(t('security.enterEmailCode'))
    return
  }
  emailLoading.value = true
  try {
    await authApi.changeEmail(emailForm.new_email, emailForm.code)
    message.success(t('security.emailChanged'))
    Object.assign(emailForm, { new_email: '', code: '' })
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('security.emailChangeFailed'))
  } finally {
    emailLoading.value = false
  }
}

async function confirmDeactivate() {
  if (!deactivatePassword.value) {
    message.warning(t('auth.password'))
    return
  }
  deactivating.value = true
  try {
    await userStore.deactivate(deactivatePassword.value)
    message.success(t('security.deactivated'))
    deactivateVisible.value = false
    router.push('/login')
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.operationFailed'))
  } finally {
    deactivating.value = false
  }
}

function openDeactivate() {
  deactivatePassword.value = ''
  deactivateVisible.value = true
}
function cancelDeactivate() {
  deactivateVisible.value = false
}

// 换绑邮箱前的二次确认（关键操作需确认）
function requestChangeEmail() {
  dialog.warning({
    title: t('security.confirmEmailChange'),
    content: `${t('security.newEmail')}: ${emailForm.new_email}`,
    positiveText: t('security.confirmEmailChange'),
    negativeText: t('action.cancel'),
    onPositiveClick: () => onChangeEmail(),
  })
}
</script>

<template>
  <div class="page-stack">
    <div class="security-grid">
      <n-card :title="t('security.changePassword')" :bordered="false">
        <n-form label-placement="top">
          <n-form-item :label="t('security.oldPassword')">
            <n-input
              v-model:value="pwdForm.old_password"
              type="password"
              show-password-on="click"
              autocomplete="current-password"
            />
          </n-form-item>
          <n-form-item :label="t('security.newPassword')">
            <n-input
              v-model:value="pwdForm.new_password"
              type="password"
              show-password-on="click"
              autocomplete="new-password"
            />
          </n-form-item>
          <n-form-item :label="t('security.confirmNewPassword')">
            <n-input
              v-model:value="pwdForm.confirm"
              type="password"
              show-password-on="click"
              @keyup.enter="onChangePassword"
            />
          </n-form-item>
          <n-button type="primary" :loading="pwdLoading" @click="onChangePassword">{{
            t('security.changePassword')
          }}</n-button>
        </n-form>
      </n-card>

      <n-card :title="t('security.changeEmail')" :bordered="false">
        <n-form label-placement="top">
          <n-form-item :label="t('security.newEmail')">
            <n-input v-model:value="emailForm.new_email" placeholder="you@example.com" />
          </n-form-item>
          <n-form-item :label="t('auth.code')">
            <div class="code-row">
              <n-input
                v-model:value="emailForm.code"
                maxlength="6"
                :placeholder="t('auth.code')"
                @keyup.enter="requestChangeEmail"
              />
              <n-button :disabled="countdown > 0" :loading="sending" @click="onSendEmailCode">
                {{ countdown > 0 ? t('auth.resend', { seconds: countdown }) : t('auth.getCode') }}
              </n-button>
            </div>
          </n-form-item>
          <n-button type="primary" :loading="emailLoading" @click="requestChangeEmail">{{
            t('security.confirmEmailChange')
          }}</n-button>
        </n-form>
      </n-card>
    </div>

    <!-- 危险区：唯一保留描边底色的分区，提示不可逆操作 -->
    <n-card :title="t('security.danger')" :bordered="false" class="danger-card">
      <div class="danger-content">
        <div>
          <strong>{{ t('security.deactivate') }}</strong>
          <p>{{ t('security.deactivateDescription') }}</p>
        </div>
        <n-button type="error" secondary @click="openDeactivate">{{
          t('security.deactivate')
        }}</n-button>
      </div>
    </n-card>

    <!-- 注销确认：输入密码后执行软注销 -->
    <n-modal
      v-model:show="deactivateVisible"
      preset="dialog"
      type="warning"
      :title="t('security.deactivateTitle')"
      :positive-text="t('security.deactivateConfirm')"
      :negative-text="t('action.cancel')"
      :loading="deactivating"
      @positive-click="confirmDeactivate"
      @negative-click="cancelDeactivate"
    >
      <p>{{ t('security.deactivatePrompt') }}</p>
      <n-input
        v-model:value="deactivatePassword"
        type="password"
        show-password-on="click"
        :placeholder="t('auth.password')"
      />
    </n-modal>
  </div>
</template>

<style scoped>
.security-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.code-row {
  display: flex;
  gap: 10px;
  width: 100%;
}
.code-row > :first-child {
  flex: 1;
}
.danger-card {
  border: 1px solid rgba(208, 48, 80, 0.35);
  background: rgba(208, 48, 80, 0.04);
}
html.dark .danger-card {
  background: rgba(208, 48, 80, 0.08);
}
.danger-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}
.danger-content strong {
  font-size: 15px;
}
.danger-content p {
  margin: 6px 0 0;
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.55;
}
@media (max-width: 720px) {
  .security-grid {
    grid-template-columns: 1fr;
  }
  .danger-content {
    align-items: start;
    flex-direction: column;
  }
  .danger-content .n-button {
    width: 100%;
  }
}
</style>
