<script setup lang="ts">
/**
 * 用户设置外壳：页面标题取自路由 meta.titleKey。
 * 个人资料 / 安全设置 / 会话管理 / 组织中心为并列页面，顶部提供路由级 Tabs 导航。
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

import PageShell from '@/components/common/PageShell.vue'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

const route = useRoute()
const { t } = useI18n()

const title = computed(() => {
  const key = route.meta.titleKey
  return key ? t(String(key)) : t('nav.userSettings')
})

const active = computed(() => {
  if (route.name === 'user-security') return 'security'
  if (route.name === 'user-sessions') return 'sessions'
  if (route.path.startsWith('/orgs')) return 'orgs'
  return 'profile'
})
</script>

<template>
  <PageShell :title="title">
    <Tabs :model-value="active" class="mb-4">
      <TabsList class="w-fit max-w-full overflow-x-auto">
        <TabsTrigger value="profile" as-child class="px-3 text-[12.5px]">
          <RouterLink to="/user/profile">{{ t('user.profile') }}</RouterLink>
        </TabsTrigger>
        <TabsTrigger value="security" as-child class="px-3 text-[12.5px]">
          <RouterLink to="/user/security">{{ t('user.security') }}</RouterLink>
        </TabsTrigger>
        <TabsTrigger value="sessions" as-child class="px-3 text-[12.5px]">
          <RouterLink to="/user/sessions">{{ t('user.sessions') }}</RouterLink>
        </TabsTrigger>
        <TabsTrigger value="orgs" as-child class="px-3 text-[12.5px]">
          <RouterLink to="/orgs/mine">{{ t('nav.orgs') }}</RouterLink>
        </TabsTrigger>
      </TabsList>
    </Tabs>
    <slot />
  </PageShell>
</template>