<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

/** 后台空间内头像菜单提供「回到前台」，前台则对管理员提供「管理后台」入口 */
const isAdminArea = computed(() => route.path.startsWith('/admin'))
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
  <div class="user-menu">
    <template v-if="userStore.isLoggedIn && userStore.user">
      <el-dropdown trigger="click" placement="bottom-end" @command="go">
        <button type="button" class="user-menu__trigger">
          <span class="user-menu__name">{{ userStore.user.nickname }}</span>
          <el-avatar :size="32" :src="avatarSrc">{{ avatarText }}</el-avatar>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-if="isAdminArea" command="/">{{ t('admin.backToApp') }}</el-dropdown-item>
            <el-dropdown-item v-else-if="userStore.isAdmin" command="/admin/users" class="user-menu__admin">{{ t('nav.admin') }}</el-dropdown-item>
            <el-dropdown-item divided command="/user/profile">{{ t('user.profile') }}</el-dropdown-item>
            <el-dropdown-item command="/user/security">{{ t('user.security') }}</el-dropdown-item>
            <el-dropdown-item command="/user/sessions">{{ t('user.sessions') }}</el-dropdown-item>
            <el-dropdown-item divided @click="onLogout">{{ t('user.logout') }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </template>

    <template v-else>
      <el-button text @click="go('/login')">{{ t('user.login') }}</el-button>
      <el-button type="primary" plain @click="go('/register')">{{ t('user.register') }}</el-button>
    </template>
  </div>
</template>

<style scoped>
.user-menu { display: flex; align-items: center; gap: 8px; }

.user-menu__trigger {
  display: flex; align-items: center; gap: 9px;
  padding: 5px 6px 5px 14px;
  border: 0; border-radius: 999px;
  background: transparent;
  color: var(--app-text); font: inherit;
  cursor: pointer;
  transition: background .18s;
}
.user-menu__trigger:hover { background: var(--app-surface-muted); }
.user-menu__trigger:focus-visible { outline: none; box-shadow: 0 0 0 3px var(--el-color-primary-light-7); }
.user-menu__trigger :deep(.el-avatar) { border: 2px solid var(--el-color-primary-light-8); }

.user-menu__name {
  max-width: 140px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-size: 13.5px; font-weight: 650;
}

.user-menu :deep(.user-menu__admin) { font-weight: 680; }

@media (max-width: 767px) {
  .user-menu__name { display: none; }
}
</style>
