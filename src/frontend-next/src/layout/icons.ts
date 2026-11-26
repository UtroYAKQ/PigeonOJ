import type { Component } from 'vue'
import {
  Activity,
  Building2,
  FileText,
  Flag,
  Gauge,
  Image,
  LayoutDashboard,
  Library,
  ListChecks,
  MonitorSmartphone,
  Settings,
  SquareCode,
  Tag,
  Tags,
  Trophy,
  User,
  Users,
} from '@lucide/vue'

/** 路由 meta.icon（沿用旧命名）→ lucide 图标组件 */
const ICONS: Record<string, Component> = {
  HomeFilled: Activity,
  Home: Activity,
  Collection: Library,
  Document: FileText,
  Trophy,
  UserFilled: Users,
  Users,
  OfficeBuilding: Building2,
  Code: SquareCode,
  Monitor: LayoutDashboard,
  User,
  Picture: Image,
  Aim: MonitorSmartphone,
  Setting: Settings,
  Settings,
  Odometer: Gauge,
  Warning: Flag,
  PriceTag: Tag,
  Tag,
  Lock: Settings,
  ListChecks,
  Tags,
}

export function resolveIcon(name?: string): Component | undefined {
  if (!name) return undefined
  return ICONS[name]
}
