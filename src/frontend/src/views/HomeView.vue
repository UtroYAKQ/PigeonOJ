<script setup lang="ts">
import { ArrowRight, Collection, Trophy, UserFilled } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const { t } = useI18n()
const greeting = computed(() => {
  if (!userStore.isLoggedIn) return t('home.welcome')
  const hour = new Date().getHours()
  const key =
    hour < 6
      ? 'dawn'
      : hour < 12
        ? 'morning'
        : hour < 14
          ? 'noon'
          : hour < 18
            ? 'afternoon'
            : 'evening'
  return `${t(`home.${key}`)}，${userStore.user?.nickname ?? t('home.student')}`
})
const cards = [
  {
    titleKey: 'nav.problems',
    descKey: 'home.problems',
    to: '/problems',
    icon: Collection,
    tone: 'primary',
  },
  {
    titleKey: 'nav.contests',
    descKey: 'home.contests',
    to: '/contests',
    icon: Trophy,
    tone: 'warning',
  },
  {
    titleKey: 'nav.teams',
    descKey: 'home.teams',
    to: '/teams',
    icon: UserFilled,
    tone: 'success',
  },
]
</script>

<template>
  <div class="home">
    <!-- 欢迎横幅：主色描边卡片（工作台欢迎区） -->
    <n-card class="home__hero" :bordered="false">
      <div class="home__hero-body">
        <p class="home__kicker">{{ t('app.name') }}</p>
        <h1>{{ greeting }}</h1>
        <p class="home__intro">{{ t('home.intro') }}</p>
        <div v-if="!userStore.isLoggedIn" class="home__hero-actions">
          <n-button type="primary" @click="router.push('/register')">
            {{ t('home.createAccount') }}
            <n-icon class="home__arrow" :component="ArrowRight" />
          </n-button>
          <n-button secondary @click="router.push('/login')">{{ t('user.login') }}</n-button>
        </div>
      </div>
      <div class="home__hero-art" aria-hidden="true"><span>🐦</span></div>
    </n-card>

    <section>
      <h2 class="home__section-title">{{ t('home.explore') }}</h2>
      <div class="home__cards">
        <button
          v-for="card in cards"
          :key="card.to"
          type="button"
          class="nav-card"
          @click="router.push(card.to)"
        >
          <span class="nav-card__icon" :class="`nav-card__icon--${card.tone}`">
            <n-icon size="18" :component="card.icon" />
          </span>
          <span class="nav-card__content">
            <strong>{{ t(card.titleKey) }}</strong>
            <small>{{ t(card.descKey) }}</small>
          </span>
          <n-icon class="nav-card__arrow" :component="ArrowRight" />
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home {
  display: grid;
  gap: 16px;
}
.home__hero :deep(.n-card__content) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}
.home__kicker {
  margin: 0 0 8px;
  color: var(--app-primary);
  font-size: 13px;
  font-weight: 600;
}
.home h1 {
  margin: 0;
  max-width: 640px;
  font-size: clamp(20px, 2.6vw, 28px);
  line-height: 1.3;
}
.home__intro {
  margin: 10px 0 0;
  max-width: 560px;
  color: var(--app-text-secondary);
  font-size: 14px;
  line-height: 1.7;
}
.home__hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
}
.home__arrow {
  margin-left: 4px;
}
.home__hero-art {
  width: 88px;
  height: 88px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 12px;
  background: var(--app-muted-bg);
}
.home__hero-art span {
  font-size: 44px;
}
.home__section-title {
  margin: 0 0 4px;
  font-size: 16px;
}
.home__cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.nav-card {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 16px;
  text-align: left;
  border: 1px solid transparent;
  border-radius: 6px;
  background: #ffffff;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}
.nav-card:hover {
  border-color: color-mix(in srgb, var(--app-primary) 45%, transparent);
  box-shadow: 0 2px 10px rgba(244, 81, 30, 0.1);
}
.nav-card:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--app-primary);
}
.nav-card__icon {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 6px;
}
.nav-card__icon--primary {
  color: var(--app-primary);
  background: rgba(244, 81, 30, 0.09);
}
.nav-card__icon--warning {
  color: #f0a020;
  background: rgba(240, 160, 32, 0.1);
}
.nav-card__icon--success {
  color: #18a058;
  background: rgba(24, 160, 88, 0.1);
}
.nav-card__content {
  display: grid;
  gap: 3px;
  min-width: 0;
}
.nav-card__content strong {
  font-size: 14px;
  color: var(--app-text);
}
.nav-card__content small {
  color: var(--app-text-secondary);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.nav-card__arrow {
  margin-left: auto;
  color: var(--app-text-secondary);
}
@media (max-width: 680px) {
  .home__hero-art {
    display: none;
  }
  .home__cards {
    grid-template-columns: 1fr;
  }
}
</style>
