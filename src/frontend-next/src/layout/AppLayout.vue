<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useEventListener, useLocalStorage } from '@vueuse/core'
import { PanelLeft, Search } from '@lucide/vue'

import AppSidebar, { type NavGroup, type NavItem } from '@/layout/AppSidebar.vue'
import CommandPalette, { type CommandItem } from '@/layout/CommandPalette.vue'
import CrumbsBar from '@/layout/CrumbsBar.vue'
import LocaleMenu from '@/layout/LocaleMenu.vue'
import ThemeToggle from '@/layout/ThemeToggle.vue'
import { resolveIcon } from '@/layout/icons'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet'
import { TooltipHint } from '@/components/ui/tooltip'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const appStore = useAppStore()
const userStore = useUserStore()

const railCollapsed = useLocalStorage('pigeonoj.console-rail-collapsed', false)
const mobileNavOpen = ref(false)
const commandOpen = ref(false)
const scroller = ref<HTMLElement | null>(null)

const isAdminArea = computed(() => route.path.startsWith('/admin'))

const isStaff = computed(() => userStore.isAdmin)

const frontItems = computed<NavItem[]>(() => [
  { key: '/', label: t('nav.home'), icon: resolveIcon('HomeFilled') },
  { key: '/problems', label: t('nav.problems'), icon: resolveIcon('Collection') },
  { key: '/problem-sets', label: t('nav.problemSets'), icon: resolveIcon('Document') },
  { key: '/contests', label: t('nav.contests'), icon: resolveIcon('Trophy') },
  { key: '/teams', label: t('nav.teams'), icon: resolveIcon('UserFilled') },
  { key: '/codes', label: t('nav.codePlaza'), icon: resolveIcon('Code') },
])

const adminGroups = computed<NavGroup[]>(() => {
  const groups: NavGroup[] = [
    {
      label: t('app.groupContent'),
      items: [
        { key: '/admin/problems', label: t('nav.problemsManage'), icon: resolveIcon('Collection') },
        {
          key: '/admin/problem-sets',
          label: t('nav.problemSetsManage'),
          icon: resolveIcon('Document'),
        },
        { key: '/admin/contests', label: t('nav.contestsManage'), icon: resolveIcon('Trophy') },
        { key: '/admin/tags', label: t('nav.tags'), icon: resolveIcon('PriceTag') },
      ],
    },
  ]
  if (userStore.isAdmin) {
    groups.push({
      label: t('app.groupCommunity'),
      items: [
        { key: '/admin/users', label: t('nav.users'), icon: resolveIcon('User') },
        { key: '/admin/teams', label: t('nav.teamsManage'), icon: resolveIcon('UserFilled') },
        { key: '/admin/orgs', label: t('nav.orgsManage'), icon: resolveIcon('OfficeBuilding') },
        { key: '/admin/reports', label: t('nav.reports'), icon: resolveIcon('Warning') },
        { key: '/admin/solutions', label: t('nav.solutionsManage'), icon: resolveIcon('Document') },
        { key: '/admin/codes', label: t('nav.codesManage'), icon: resolveIcon('Code') },
      ],
    })
    groups.push({
      label: t('app.groupData'),
      items: [
        {
          key: '/admin/submissions',
          label: t('nav.submissionsManage'),
          icon: resolveIcon('Document'),
        },
        { key: '/admin/logs', label: t('nav.logs'), icon: resolveIcon('Document') },
        { key: '/admin/online', label: t('nav.onlineUsers'), icon: resolveIcon('Aim') },
      ],
    })
    groups.push({
      label: t('app.groupSystem'),
      items: [
        { key: '/admin/home', label: t('nav.homeConfig'), icon: resolveIcon('Picture') },
        { key: '/admin/configs', label: t('nav.configs'), icon: resolveIcon('Setting') },
        { key: '/admin/sandbox', label: t('nav.sandbox'), icon: resolveIcon('Odometer') },
      ],
    })
  }
  return groups
})

const sidebarGroups = computed<NavGroup[]>(() => {
  if (isAdminArea.value) return adminGroups.value
  return [{ label: t('app.groupBrowse'), items: frontItems.value }]
})

const allNavItems = computed<NavItem[]>(() => [
  ...frontItems.value,
  ...adminGroups.value.flatMap((group) => group.items),
])

const activeKey = computed(() => {
  const path = route.path
  const hits = allNavItems.value
    .map((item) => item.key)
    .filter((key) => (key === '/' ? path === '/' : path === key || path.startsWith(`${key}/`)))
    .sort((a, b) => b.length - a.length)
  return hits[0] ?? path
})

const commandItems = computed<CommandItem[]>(() => {
  const items: CommandItem[] = allNavItems.value.map((item) => ({
    key: item.key,
    label: item.label,
    group: isStaff.value ? t('app.groupNav') : t('app.groupPages'),
    icon: item.icon,
    run: () => router.push(item.key),
  }))
  if (userStore.isLoggedIn) {
    items.push({
      key: '/user/profile',
      label: t('user.profile'),
      group: t('app.groupAccount'),
      icon: resolveIcon('User'),
      run: () => router.push('/user/profile'),
    })
  }
  return items
})

const shortcutKey = computed(() =>
  typeof navigator !== 'undefined' && navigator.userAgent.includes('Mac') ? '⌘' : 'Ctrl',
)

const cacheScope = computed(() => userStore.user?.id ?? 'anon')

useEventListener(window, 'keydown', (event: KeyboardEvent) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    commandOpen.value = !commandOpen.value
  }
})

function toggleRail(): void {
  if (window.matchMedia('(min-width: 1024px)').matches) {
    railCollapsed.value = !railCollapsed.value
  } else {
    mobileNavOpen.value = true
  }
}

function selectNav(key: string): void {
  router.push(key)
}

function backToWorkspace(): void {
  router.push('/')
}

watch(
  () => route.fullPath,
  () => {
    scroller.value?.scrollTo({ top: 0 })
  },
)
</script>

<template>
  <div class="flex h-dvh w-full overflow-hidden bg-background text-foreground">
    <aside
      class="hidden h-full shrink-0 overflow-hidden transition-[width] duration-200 ease-linear lg:block"
      :class="railCollapsed ? 'w-0 border-r-0' : 'w-64 border-r border-sidebar-border'"
    >
      <AppSidebar
        :area="isAdminArea ? 'admin' : 'front'"
        :groups="sidebarGroups"
        :active="activeKey"
        @select="selectNav"
        @back="backToWorkspace"
      />
    </aside>

    <div class="flex min-h-0 min-w-0 flex-1 flex-col">
      <header class="flex h-14 shrink-0 items-center gap-2 border-b border-border/70 px-3 sm:px-4">
        <TooltipHint :text="railCollapsed ? t('app.expandRail') : t('app.collapseRail')">
          <button
            type="button"
            class="grid size-9 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            :aria-label="railCollapsed ? t('app.expandRail') : t('app.collapseRail')"
            @click="toggleRail"
          >
            <PanelLeft class="size-[18px]" :stroke-width="1.8" />
          </button>
        </TooltipHint>

        <div class="hidden min-w-0 items-center sm:flex">
          <CrumbsBar />
        </div>

        <button
          type="button"
          class="hidden h-8 w-[224px] items-center gap-2 rounded-md border border-border bg-background px-2.5 text-[13px] text-muted-foreground transition-colors hover:bg-muted/50 xl:flex"
          @click="commandOpen = true"
        >
          <Search class="size-3.5 shrink-0" />
          <span class="flex-1 text-left">{{ t('app.searchMenu') }}</span>
          <span class="flex items-center gap-1">
            <span class="rounded border border-border bg-muted px-1 py-0.5 text-[9px] leading-none">
              {{ shortcutKey }}
            </span>
            <span class="rounded border border-border bg-muted px-1 py-0.5 text-[9px] leading-none"
              >K</span
            >
          </span>
        </button>

        <button
          type="button"
          class="grid size-8 place-items-center rounded-md border border-border bg-background text-muted-foreground transition-colors hover:bg-muted hover:text-foreground xl:hidden"
          :aria-label="t('app.searchMenu')"
          @click="commandOpen = true"
        >
          <Search class="size-3.5" />
        </button>

        <div class="ml-auto flex items-center gap-1.5">
          <LocaleMenu />
          <ThemeToggle />
        </div>
      </header>

      <main ref="scroller" class="min-h-0 flex-1 overflow-y-auto">
        <router-view v-slot="{ Component, route: current }" :key="cacheScope">
          <keep-alive :max="8">
            <component :is="Component" v-if="current.meta.keepAlive" :key="current.fullPath" />
          </keep-alive>
          <component :is="Component" v-if="!current.meta.keepAlive" :key="current.fullPath" />
        </router-view>
      </main>

      <footer
        v-if="appStore.siteConfig.icp"
        class="shrink-0 border-t border-border/70 py-1.5 text-center text-[12px] text-muted-foreground"
      >
        {{ appStore.siteConfig.icp }}
      </footer>
    </div>

    <Sheet v-model:open="mobileNavOpen">
      <SheetContent
        side="left"
        :show-close-button="false"
        class="w-[284px] max-w-[86vw] border-r border-sidebar-border bg-sidebar p-0"
      >
        <SheetTitle class="sr-only">{{ t('app.navTitle') }}</SheetTitle>
        <SheetDescription class="sr-only">{{ t('app.navDesc') }}</SheetDescription>
        <AppSidebar
          :area="isAdminArea ? 'admin' : 'front'"
          :groups="sidebarGroups"
          :active="activeKey"
          mobile
          @select="selectNav"
          @close="mobileNavOpen = false"
          @back="backToWorkspace"
        />
      </SheetContent>
    </Sheet>

    <CommandPalette v-model:open="commandOpen" :items="commandItems" />
  </div>
</template>
