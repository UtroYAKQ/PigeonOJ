/**
 * 侧边栏 / 二级菜单图标映射：meta.icon 字符串 → Element Plus 图标组件。
 */
import {
  Collection,
  Document,
  HomeFilled,
  Lock,
  Monitor,
  Odometer,
  Setting,
  Trophy,
  User,
  UserFilled,
  Warning,
} from '@element-plus/icons-vue'
import type { Component } from 'vue'

export const iconMap: Record<string, Component> = {
  HomeFilled,
  Collection,
  Trophy,
  UserFilled,
  Monitor,
  Setting,
  User,
  Lock,
  Odometer,
  Document,
  Warning,
}

export function resolveIcon(name?: string): Component | null {
  if (!name) return null
  return iconMap[name] ?? null
}
