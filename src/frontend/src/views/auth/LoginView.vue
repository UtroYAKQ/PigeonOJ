<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'
import { message } from '@/utils/feedback'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const appStore = useAppStore()
const { t } = useI18n()
const form = reactive({ email: '', password: '' })
const loading = ref(false)
async function onSubmit() {
  if (!form.email || !form.password) {
    message.warning(t('auth.enterEmailPassword'))
    return
  }
  loading.value = true
  try {
    await userStore.login(form.email, form.password)
    message.success(t('auth.loginSuccess'))
    router.push(
      typeof route.query.redirect === 'string' && route.query.redirect ? route.query.redirect : '/',
    )
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('auth.loginFailed'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <!-- 左侧品牌区：深色底 + 白字，参考模板登录页分栏 -->
    <section class="brand-pane">
      <header class="brand-pane__top" @click="router.push('/')">
        <span class="brand-pane__mark">🐦</span>
        <strong>{{ appStore.siteConfig.name || 'PigeonOJ' }}</strong>
      </header>
      <div class="brand-pane__body">
        <h1>{{ t('auth.loginTitle') }}</h1>
        <p>{{ t('home.intro') }}</p>
      </div>
      <footer class="brand-pane__foot">{{ t('app.tagline') }}</footer>
    </section>

    <main class="form-pane">
      <n-card class="login-card" :bordered="false">
        <h2 class="login-card__title">{{ t('user.login') }}</h2>
        <n-form label-placement="top" @submit.prevent="onSubmit">
          <n-form-item :label="t('auth.email')">
            <n-input
              v-model:value="form.email"
              size="large"
              placeholder="you@example.com"
              autocomplete="username"
            />
          </n-form-item>
          <n-form-item :label="t('auth.password')">
            <n-input
              v-model:value="form.password"
              type="password"
              show-password-on="click"
              size="large"
              :placeholder="t('auth.passwordPlaceholder')"
              autocomplete="current-password"
              @keyup.enter="onSubmit"
            />
          </n-form-item>
          <n-button type="primary" size="large" block :loading="loading" attr-type="submit">
            {{ t('user.login') }}
          </n-button>
        </n-form>
        <p class="login-card__footer">
          {{ t('auth.noAccount') }}
          <n-button text type="primary" @click="router.push('/register')">{{
            t('auth.registerNow')
          }}</n-button>
        </p>
      </n-card>
    </main>
  </div>
</template>

<style scoped>
.login-page {
  display: grid;
  grid-template-columns: minmax(360px, 1.05fr) minmax(420px, 0.95fr);
  min-height: 100dvh;
  background: #ffffff;
}
.brand-pane {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 40px;
  padding: 36px clamp(28px, 6vw, 80px);
  background: #2b4c59;
  color: rgba(255, 255, 255, 0.92);
}
.brand-pane__top {
  display: flex;
  align-items: center;
  gap: 10px;
  width: max-content;
  font-size: 17px;
  cursor: pointer;
}
.brand-pane__mark {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.12);
  font-size: 20px;
}
.brand-pane h1 {
  margin: 0 0 14px;
  max-width: 480px;
  font-size: clamp(26px, 3vw, 34px);
  line-height: 1.25;
}
.brand-pane p {
  margin: 0;
  max-width: 460px;
  font-size: 14px;
  line-height: 1.75;
  color: rgba(255, 255, 255, 0.72);
}
.brand-pane__foot {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
}
.form-pane {
  display: grid;
  place-items: center;
  padding: 32px;
}
.login-card {
  width: min(100%, 400px);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.login-card__title {
  margin: 0 0 22px;
  font-size: 20px;
}
.login-card__footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin: 18px 0 0;
  color: var(--app-text-secondary);
  font-size: 13px;
}
@media (max-width: 800px) {
  .login-page {
    grid-template-columns: 1fr;
  }
  .brand-pane {
    padding: 24px;
  }
  .brand-pane__body {
    display: none;
  }
  .brand-pane__foot {
    display: none;
  }
}
</style>
