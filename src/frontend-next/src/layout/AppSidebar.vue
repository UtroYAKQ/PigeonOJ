<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, Building2, ChevronUp, LayoutDashboard, LogOut, UserRound, X } from '@lucide/vue'

import BrandMark from '@/layout/BrandMark.vue'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'

export interface NavItem {
  key: string
  label: string
  icon?: unknown
  badge?: string | number
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

const props = defineProps<{
  area: 'front' | 'admin'
  groups: NavGroup[]
  active: string
  mobile?: boolean
}>()

const emit = defineEmits<{
  select: [key: string]
  close: []
  back: []
}>()

const router = useRouter()
const { t } = useI18n()
const appStore = useAppStore()
const userStore = useUserStore()

const subtitle = computed(() => (props.area === 'admin' ? t('nav.admin') : t('app.tagline')))
const isStaff = computed(() => userStore.isAdmin)

function select(key: string): void {
  emit('select', key)
  if (props.mobile) emit('close')
}

function closeIfMobile(): void {
  if (props.mobile) emit('close')
}

function go(path: string): void {
  router.push(path)
  closeIfMobile()
}

async function logout(): Promise<void> {
  await userStore.logout()
  void router.replace('/login')
  closeIfMobile()
}
</script>

<template>
  <div class="flex h-full flex-col bg-sidebar text-sidebar-foreground">
    <div class="flex h-14 shrink-0 items-center gap-1 px-3">
      <router-link
        to="/"
        class="flex min-w-0 flex-1 items-center gap-2.5 rounded-md px-1 py-1 transition-colors hover:bg-sidebar-accent/60"
        @click="props.mobile && emit('close')"
      >
        <BrandMark size="sm" />
        <span class="min-w-0 flex-1">
          <span class="block truncate text-[13.5px] font-semibold leading-4">
            {{ appStore.siteName }}
          </span>
          <span class="block truncate text-[11.5px] leading-4 text-muted-foreground">
            {{ subtitle }}
          </span>
        </span>
      </router-link>
      <button
        v-if="mobile"
        type="button"
        class="grid size-8 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
        :aria-label="t('app.closeNav')"
        @click="emit('close')"
      >
        <X class="size-4" />
      </button>
    </div>

    <ScrollArea class="min-h-0 flex-1">
      <nav class="px-2.5 pb-4">
      <template v-for="group in groups" :key="group.label">
        <p class="px-2.5 pb-1 pt-3 text-[11.5px] font-medium text-muted-foreground">
          {{ group.label }}
        </p>
        <div class="space-y-0.5">
          <button
            v-for="item in group.items"
            :key="item.key"
            type="button"
            class="flex h-9 w-full items-center gap-2.5 rounded-md border px-2.5 text-[13.5px] transition-colors"
            :class="
              active === item.key
                ? 'border-sidebar-border bg-background font-medium text-sidebar-foreground'
                : 'border-transparent text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-foreground'
            "
            :aria-current="active === item.key ? 'page' : undefined"
            @click="select(item.key)"
          >
            <component
              :is="item.icon"
              v-if="item.icon"
              class="size-[17px] shrink-0"
              :stroke-width="1.8"
            />
            <span class="min-w-0 flex-1 truncate text-left">{{ item.label }}</span>
            <span v-if="item.badge" class="text-[11px] tabular-nums text-muted-foreground">
              {{ item.badge }}
            </span>
          </button>
        </div>
      </template>
    </nav>
    </ScrollArea>

    <div class="border-t border-sidebar-border/80 p-2.5">
      <button
        v-if="area === 'admin'"
        type="button"
        class="mb-1 flex h-9 w-full items-center gap-2.5 rounded-md px-2.5 text-[13px] text-muted-foreground transition-colors hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
        @click="emit('back')"
      >
        <ArrowLeft class="size-4" />
        {{ t('admin.backToApp') }}
      </button>

      <DropdownMenu v-if="userStore.user">
        <DropdownMenuTrigger as-child>
          <button
            type="button"
            class="flex w-full items-center gap-2.5 rounded-md px-1.5 py-1.5 text-left transition-colors hover:bg-sidebar-accent/60"
            :aria-label="t('app.accountMenu')"
          >
            <BaseAvatar
              :src="userStore.user.avatar_url"
              :name="userStore.user.nickname"
              :size="30"
            />
            <span class="min-w-0 flex-1">
              <span class="block truncate text-[13px] font-medium leading-4">
                {{ userStore.user.nickname }}
              </span>
              <span class="block truncate text-[11.5px] leading-4 text-muted-foreground">
                {{ userStore.user.email }}
              </span>
            </span>
            <ChevronUp class="size-3.5 shrink-0 text-muted-foreground" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent side="top" align="start" class="w-[232px]">
          <DropdownMenuItem class="cursor-pointer text-[13px]" @select="go('/user/profile')">
            <UserRound class="mr-2 size-4" />
            {{ t('user.profile') }}
          </DropdownMenuItem>
          <DropdownMenuItem class="cursor-pointer text-[13px]" @select="go('/orgs/mine')">
            <Building2 class="mr-2 size-4" />
            {{ t('nav.orgs') }}
          </DropdownMenuItem>
          <DropdownMenuItem
            v-if="area !== 'admin' && isStaff"
            class="cursor-pointer text-[13px]"
            @select="go('/admin/problems')"
          >
            <LayoutDashboard class="mr-2 size-4" />
            {{ t('nav.admin') }}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem class="cursor-pointer text-[13px]" @select="logout">
            <LogOut class="mr-2 size-4" />
            {{ t('user.logout') }}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <div v-else class="grid grid-cols-2 gap-2">
        <Button variant="outline" size="toolbar" @click="go('/login')">
          {{ t('user.login') }}
        </Button>
        <Button size="toolbar" @click="go('/register')">
          {{ t('user.register') }}
        </Button>
      </div>
    </div>
  </div>
</template>
