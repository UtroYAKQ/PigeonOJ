<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { buildCrumbs } from '@/router/crumbs'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const crumbs = computed(() => buildCrumbs(route, (key) => t(key)))
</script>

<template>
  <Breadcrumb v-if="crumbs.length" class="min-w-0 overflow-hidden text-[13px]">
    <BreadcrumbList class="min-w-0 flex-nowrap overflow-hidden">
      <template v-for="(crumb, index) in crumbs" :key="`${index}-${crumb.label}`">
        <BreadcrumbItem>
          <BreadcrumbLink v-if="crumb.to" as-child>
            <button
              type="button"
              class="truncate text-muted-foreground"
              @click="router.push(crumb.to)"
            >
              {{ crumb.label }}
            </button>
          </BreadcrumbLink>
          <BreadcrumbPage v-else class="truncate font-medium">{{ crumb.label }}</BreadcrumbPage>
        </BreadcrumbItem>
        <BreadcrumbSeparator v-if="index < crumbs.length - 1" />
      </template>
    </BreadcrumbList>
  </Breadcrumb>
</template>
