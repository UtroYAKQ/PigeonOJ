<script setup lang="ts">
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
</script>

<template>
  <el-container class="app-layout">
    <el-aside :width="appStore.sidebarCollapsed ? '64px' : '200px'">
      <el-menu
        class="app-menu"
        :collapse="appStore.sidebarCollapsed"
        :collapse-transition="false"
        router
      >
        <div class="logo">PigeonOJ</div>
        <el-menu-item index="/">首页</el-menu-item>
        <!-- 业务菜单随后续各模块逐步加入 -->
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <el-button text @click="appStore.toggleSidebar()">
          {{ appStore.sidebarCollapsed ? '展开' : '收起' }}
        </el-button>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.app-layout {
  height: 100vh;
}

.logo {
  height: 48px;
  line-height: 48px;
  text-align: center;
  font-weight: 600;
}

.app-header {
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--el-border-color);
}
</style>
