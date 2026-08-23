<script setup lang="ts">
import { SwitchButton } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { ROLE_NAME } from '@/constants/dict'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const { t } = useI18n()
const appStore = useAppStore()
const userStore = useUserStore()

const collapsed = computed(() => appStore.sidebarCollapsed)

const roleLabels = computed(() => (userStore.user?.roles ?? []).map((r) => ROLE_NAME[r] ?? r).join(' / '))

const avatarText = computed(() => (userStore.user?.nickname ?? '?').slice(0, 1))
const avatarSrc = computed(() => {
  const value = userStore.user?.avatar_url
  if (!value) return undefined
  return value.startsWith('http://') || value.startsWith('https://') ? value : `/api/v1/files/${value}`
})

function go(path: string) {
  router.push(path)
}

async function onLogout() {
  await userStore.logout()
  router.push('/login')
}
</script>

<template>
  <div class="user-card" :class="{ 'is-collapsed': collapsed }">
    <template v-if="userStore.isLoggedIn && userStore.user">
      <el-dropdown trigger="click" placement="top-start" @command="go">
        <div class="user-card__main">
          <el-avatar :size="collapsed ? 34 : 40" :src="avatarSrc">
            {{ avatarText }}
          </el-avatar>
          <div v-show="!collapsed" class="user-card__info">
            <div class="user-card__name">{{ userStore.user.nickname }}</div>
            <div class="user-card__role">{{ roleLabels }}</div>
          </div>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="/user/profile">{{ t('user.profile') }}</el-dropdown-item>
            <el-dropdown-item command="/user/security">{{ t('user.security') }}</el-dropdown-item>
            <el-dropdown-item command="/user/sessions">{{ t('user.sessions') }}</el-dropdown-item>
            <el-dropdown-item divided @click="onLogout">{{ t('user.logout') }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </template>

    <template v-else>
      <el-button v-show="!collapsed" type="primary" class="user-card__login" @click="go('/login')">{{ t('user.login') }}</el-button>
      <el-button v-show="!collapsed" text class="user-card__register" @click="go('/register')">{{ t('user.register') }}</el-button>
      <el-button v-show="collapsed" text circle @click="go('/login')">
        <el-icon><SwitchButton /></el-icon>
      </el-button>
    </template>
  </div>
</template>

<style scoped>
.user-card{margin-top:8px;padding:12px 6px 2px;border-top:1px solid var(--app-border);display:flex;align-items:center;justify-content:center}.user-card:not(.is-collapsed){padding-left:8px;padding-right:8px}

.user-card__main{display:flex;align-items:center;gap:10px;cursor:pointer;width:100%;padding:8px;border-radius:12px;transition:background .18s}.user-card__main :deep(.el-avatar){border:2px solid var(--el-color-primary-light-8)}

.user-card__main:hover {
  background: var(--app-surface-muted);
}

.user-card__info {
  min-width: 0;
  flex: 1;
}

.user-card__name {
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-card__role {
  font-size: 12px;
  color: var(--app-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-card.is-collapsed .user-card__main {
  justify-content: center;
}

.user-card__login,
.user-card__register {
  width: 100%;
  margin: 2px 0;
}
</style>
