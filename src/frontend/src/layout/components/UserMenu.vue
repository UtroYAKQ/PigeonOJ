<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import type { DropdownOption } from 'naive-ui'

import { useUserStore } from '@/stores/user'
import BaseAvatar from '@/components/BaseAvatar.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

/** 后台空间内头像菜单提供「回到前台」，前台则对管理员提供「管理后台」入口 */
const isAdminArea = computed(() => route.path.startsWith('/admin'))
/** 个人面板内同样提供「回到前台」 */
const isMeArea = computed(() => route.path.startsWith('/me'))

const options = computed<DropdownOption[]>(() => {
  if (!userStore.isLoggedIn) return []
  const items: DropdownOption[] = []
  if (isAdminArea.value || isMeArea.value) {
    items.push({ label: t('admin.backToApp'), key: '/' })
  } else {
    if (userStore.isAdmin) items.push({ label: t('nav.admin'), key: '/admin/users' })
    items.push({ label: t('nav.me'), key: '/me/profile' })
  }
  items.push({ label: t('user.logout'), key: '__logout' })
  return items
})

async function onSelect(key: string) {
  if (key === '__logout') {
    await userStore.logout()
    router.push('/login')
    return
  }
  router.push(key)
}

function go(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="user-menu">
    <template v-if="userStore.isLoggedIn && userStore.user">
      <n-dropdown trigger="click" placement="bottom-end" :options="options" @select="onSelect">
        <button type="button" class="user-menu__trigger">
          <span class="user-menu__name">{{ userStore.user.nickname }}</span>
          <BaseAvatar
            :src="userStore.user?.avatar_url"
            :name="userStore.user?.nickname"
            :size="30"
          />
        </button>
      </n-dropdown>
    </template>

    <template v-else>
      <n-button quaternary size="small" @click="go('/login')">{{ t('user.login') }}</n-button>
      <n-button type="primary" size="small" @click="go('/register')">{{
        t('user.register')
      }}</n-button>
    </template>
  </div>
</template>

<style scoped>
.user-menu {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-menu__trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px 4px 10px;
  border: 0;
  border-radius: 3px;
  background: transparent;
  color: var(--app-text);
  font: inherit;
  cursor: pointer;
  transition: background-color 0.15s ease;
}
.user-menu__trigger:hover {
  background: var(--app-muted-bg);
}
.user-menu__trigger:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--app-primary);
}

.user-menu__name {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 500;
}

@media (max-width: 767px) {
  .user-menu__name {
    display: none;
  }
}
</style>
