<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { uploadAvatar } from '@/api/files'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'

const userStore = useUserStore()
const { t } = useI18n()
const form = reactive({ nickname: '', signature: '', avatar_url: '', theme: 'light' })
const saved = ref(true)
const saving = ref(false)
const uploadingAvatar = ref(false)
const avatarInput = ref<HTMLInputElement>()
watch(
  () => userStore.user,
  (u) => {
    if (u) {
      form.nickname = u.nickname ?? ''
      form.signature = u.signature ?? ''
      form.avatar_url = u.avatar_url ?? ''
      form.theme = u.theme ?? 'light'
    }
  },
  { immediate: true },
)
watch(form, () => (saved.value = false))
function avatarSrc(ossId: string) {
  return ossId ? `/api/v1/files/${ossId}` : undefined
}
async function onAvatarChosen(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const allowed = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
  if (!allowed.includes(file.type) || file.size > 2 * 1024 * 1024) {
    message.warning(t('profile.invalidAvatar'))
    input.value = ''
    return
  }
  uploadingAvatar.value = true
  try {
    const result = await uploadAvatar(file)
    form.avatar_url = result.oss_id
    message.success(t('profile.uploadSuccess'))
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('profile.uploadFailed'))
  } finally {
    uploadingAvatar.value = false
    input.value = ''
  }
}
async function onSave() {
  if (!form.nickname.trim()) {
    message.warning(t('profile.nicknameRequired'))
    return
  }
  saving.value = true
  try {
    await userStore.updateProfile({
      nickname: form.nickname.trim(),
      signature: form.signature || null,
      avatar_url: form.avatar_url || null,
      theme: form.theme as 'light' | 'dark',
    })
    saved.value = true
    message.success(t('profile.saved'))
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('config.saveFailed'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page-stack">
    <div class="profile-grid">
      <n-card :bordered="false">
        <div class="identity-avatar">
          <n-avatar round :size="104" :src="avatarSrc(form.avatar_url)">
            {{ (form.nickname || '?').slice(0, 1) }}
          </n-avatar>
          <n-button :loading="uploadingAvatar" @click="avatarInput?.click()">
            {{ form.avatar_url ? t('action.change') : t('action.upload') }}
          </n-button>
          <input
            ref="avatarInput"
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            hidden
            @change="onAvatarChosen"
          />
        </div>
        <div class="identity-user">
          <strong>{{ form.nickname || '—' }}</strong>
          <span>{{ userStore.user?.email }}</span>
        </div>
        <n-divider />
        <dl class="identity-list">
          <div>
            <dt>{{ t('profile.email') }}</dt>
            <dd>
              <span>{{ userStore.user?.email }}</span>
              <n-tag v-if="userStore.user?.email_verified" size="small" type="success" round>
                {{ t('profile.verified') }}
              </n-tag>
              <n-tag v-else size="small" type="warning" round>{{ t('profile.unverified') }}</n-tag>
            </dd>
          </div>
          <div>
            <dt>{{ t('profile.createdAt') }}</dt>
            <dd>{{ formatDateTime(userStore.user?.created_at) }}</dd>
          </div>
        </dl>
      </n-card>

      <n-card :bordered="false">
        <template #header>
          <div class="form-head">
            <span>{{ t('profile.title') }}</span>
            <div class="form-head__save">
              <n-tag v-if="!saved" type="warning" size="small" round>{{
                t('profile.unsaved')
              }}</n-tag>
              <n-button size="small" type="primary" :loading="saving" @click="onSave">{{
                t('profile.saveChanges')
              }}</n-button>
            </div>
          </div>
        </template>
        <n-form label-placement="top">
          <n-form-item :label="t('profile.nickname')">
            <n-input v-model:value="form.nickname" size="large" maxlength="64" show-count />
          </n-form-item>
          <n-form-item :label="t('profile.signature')">
            <n-input
              v-model:value="form.signature"
              size="large"
              maxlength="255"
              show-count
              :placeholder="t('profile.signatureHint')"
            />
          </n-form-item>
          <n-form-item :label="t('profile.theme')">
            <n-radio-group v-model:value="form.theme">
              <n-radio-button value="light">{{ t('profile.light') }}</n-radio-button>
              <n-radio-button value="dark">{{ t('profile.dark') }}</n-radio-button>
            </n-radio-group>
          </n-form-item>
        </n-form>
      </n-card>
    </div>
  </div>
</template>

<style scoped>
.profile-grid {
  display: grid;
  grid-template-columns: minmax(270px, 0.72fr) minmax(0, 1.28fr);
  gap: 16px;
}
.identity-avatar {
  display: grid;
  justify-items: start;
  gap: 14px;
}
.identity-user {
  display: grid;
  gap: 4px;
  margin: 22px 0 10px;
}
.identity-user strong {
  font-size: 20px;
}
.identity-user span {
  color: var(--app-text-secondary);
  font-size: 13px;
}
.identity-list {
  display: grid;
  gap: 16px;
  margin: 0;
}
.identity-list div {
  display: grid;
  gap: 6px;
}
.identity-list dt {
  color: var(--app-text-secondary);
  font-size: 12px;
  font-weight: 600;
}
.identity-list dd {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0;
  font-size: 13px;
}
.form-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}
.form-head__save {
  display: flex;
  align-items: center;
  gap: 10px;
}
@media (max-width: 760px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }
}
</style>
