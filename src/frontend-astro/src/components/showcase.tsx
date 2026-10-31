"use client"

import { useState } from "react"
import {
  ArrowUpRightIcon,
  CheckCircle2Icon,
  CircleDotIcon,
  Clock3Icon,
  Code2Icon,
  DatabaseIcon,
  LayersIcon,
  PaletteIcon,
  RocketIcon,
  ServerIcon,
  SparklesIcon,
  XCircleIcon,
} from "lucide-react"
import { toast } from "sonner"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Toaster } from "@/components/ui/sonner"

const stack = [
  { label: "Astro", value: "7.x · 静态输出", icon: RocketIcon },
  { label: "React", value: "19 · 岛屿架构", icon: LayersIcon },
  { label: "Tailwind CSS", value: "4.x · Vite 插件", icon: PaletteIcon },
  {
    label: "shadcn/ui",
    value: "radix-nova · 24 个基础组件",
    icon: SparklesIcon,
  },
]

const submissions = [
  {
    id: "S-1042",
    problem: "A + B Problem",
    language: "C++17",
    status: "Accepted",
    time: "12 ms",
    memory: "3.2 MB",
    tone: "success" as const,
  },
  {
    id: "S-1041",
    problem: "区间求和",
    language: "Python 3.12",
    status: "Time Limit Exceeded",
    time: "2001 ms",
    memory: "18.4 MB",
    tone: "warning" as const,
  },
  {
    id: "S-1040",
    problem: "最短路径",
    language: "Java 21",
    status: "Wrong Answer",
    time: "86 ms",
    memory: "42.1 MB",
    tone: "error" as const,
  },
  {
    id: "S-1039",
    problem: "树形 DP 入门",
    language: "C++17",
    status: "Judging",
    time: "—",
    memory: "—",
    tone: "muted" as const,
  },
]

const toneClass = {
  success: "bg-success/10 text-success border-success/20",
  warning: "bg-warning/10 text-warning border-warning/20",
  error: "bg-destructive/10 text-destructive border-destructive/20",
  muted: "bg-muted text-muted-foreground border-border",
} as const

function SectionTitle({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof ServerIcon
  title: string
  description: string
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
        <Icon className="size-4.5" />
      </div>
      <div className="space-y-1">
        <h2 className="font-heading text-sm font-semibold">{title}</h2>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
    </div>
  )
}

export function Showcase() {
  const [language, setLanguage] = useState("cpp17")
  const [autoRefresh, setAutoRefresh] = useState(true)

  return (
    <>
      <div className="grid gap-4">
        <Card>
          <CardHeader className="border-b">
            <SectionTitle
              icon={Code2Icon}
              title="基础组件与交互"
              description="按钮 / 表单 / 弹窗 / Toast 均为 React 岛屿，按需 hydrate。"
            />
            <CardAction>
              <Badge variant="secondary">client:load</Badge>
            </CardAction>
          </CardHeader>
          <CardContent className="space-y-6 pt-(--card-spacing)">
            <div className="flex flex-wrap items-center gap-2">
              <Button>主要按钮</Button>
              <Button variant="secondary">次要按钮</Button>
              <Button variant="outline">描边</Button>
              <Button variant="ghost">幽灵</Button>
              <Button variant="destructive">危险操作</Button>
              <Button variant="link">
                链接
                <ArrowUpRightIcon data-icon="inline-end" />
              </Button>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="demo-problem">题目搜索</Label>
                <Input id="demo-problem" placeholder="输入题目标题或 ID…" />
              </div>
              <div className="grid gap-2">
                <Label>判题语言</Label>
                <Select value={language} onValueChange={setLanguage}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="选择语言" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cpp17">C++17</SelectItem>
                    <SelectItem value="python3.12">Python 3.12</SelectItem>
                    <SelectItem value="java21">Java 21</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  当前选择：{language}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
              <div className="flex items-center gap-2">
                <Switch
                  id="demo-refresh"
                  checked={autoRefresh}
                  onCheckedChange={setAutoRefresh}
                />
                <Label htmlFor="demo-refresh">评测中自动轮询</Label>
              </div>
              <div className="flex items-center gap-2">
                <Dialog>
                  <DialogTrigger asChild>
                    <Button variant="outline">打开确认弹窗</Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>提交代码？</DialogTitle>
                      <DialogDescription>
                        此操作会占用判题队列，提交后不可撤回。演示弹窗不执行任何请求。
                      </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                      <DialogClose asChild>
                        <Button variant="outline">取消</Button>
                      </DialogClose>
                      <DialogClose asChild>
                        <Button
                          onClick={() =>
                            toast.success("演示：已提交（未调用后端）", {
                              description:
                                "真实提交需接入 /api/v1/submissions。",
                            })
                          }
                        >
                          确认提交
                        </Button>
                      </DialogClose>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
                <Button
                  variant="secondary"
                  onClick={() =>
                    toast("演示 Toast", {
                      description: "sonner 已接入，主题跟随明暗模式。",
                    })
                  }
                >
                  触发 Toast
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <Card>
            <CardHeader>
              <CardTitle>提交记录（示例数据）</CardTitle>
              <CardDescription>
                shadcn Table 组合，状态色使用 success / warning / destructive
                语义令牌。
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>提交</TableHead>
                    <TableHead>题目</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead className="text-right">耗时</TableHead>
                    <TableHead className="text-right">内存</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {submissions.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {row.id}
                        <span className="ml-2 text-[0.7rem]">
                          {row.language}
                        </span>
                      </TableCell>
                      <TableCell className="font-medium">
                        {row.problem}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={toneClass[row.tone]}
                        >
                          {row.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {row.time}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {row.memory}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
            <CardFooter className="justify-between text-xs text-muted-foreground">
              <span>示例数据 · 非真实接口</span>
              <span className="inline-flex items-center gap-1">
                <Clock3Icon className="size-3.5" />
                轮询间隔建议 2s
              </span>
            </CardFooter>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>判题状态色板</CardTitle>
              <CardDescription>
                与旧前端语义色对齐：成功 / 警告 / 错误 / 中性。
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <Badge variant="outline" className={toneClass.success}>
                  <CheckCircle2Icon data-icon="inline-start" />
                  Accepted
                </Badge>
                <code className="text-xs text-muted-foreground">--success</code>
              </div>
              <div className="flex items-center justify-between gap-3">
                <Badge variant="outline" className={toneClass.warning}>
                  <Clock3Icon data-icon="inline-start" />
                  Time Limit
                </Badge>
                <code className="text-xs text-muted-foreground">--warning</code>
              </div>
              <div className="flex items-center justify-between gap-3">
                <Badge variant="outline" className={toneClass.error}>
                  <XCircleIcon data-icon="inline-start" />
                  Wrong Answer
                </Badge>
                <code className="text-xs text-muted-foreground">
                  --destructive
                </code>
              </div>
              <div className="flex items-center justify-between gap-3">
                <Badge variant="outline" className={toneClass.muted}>
                  <CircleDotIcon data-icon="inline-start" />
                  Pending
                </Badge>
                <code className="text-xs text-muted-foreground">--muted</code>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <SectionTitle
              icon={ServerIcon}
              title="骨架能力"
              description="后续业务页面按模块增量迁移，先验证基础设施可用。"
            />
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="stack">
              <TabsList>
                <TabsTrigger value="stack">技术栈</TabsTrigger>
                <TabsTrigger value="api">API 接入</TabsTrigger>
                <TabsTrigger value="ui">组件清单</TabsTrigger>
              </TabsList>
              <TabsContent value="stack" className="pt-4">
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {stack.map((item) => (
                    <div
                      key={item.label}
                      className="rounded-lg border bg-muted/40 p-3"
                    >
                      <item.icon className="mb-2 size-4 text-primary" />
                      <p className="text-sm font-medium">{item.label}</p>
                      <p className="text-xs text-muted-foreground">
                        {item.value}
                      </p>
                    </div>
                  ))}
                </div>
              </TabsContent>
              <TabsContent value="api" className="space-y-3 pt-4">
                <p className="text-sm text-muted-foreground">
                  开发服务器已把 <code className="text-foreground">/api</code>{" "}
                  代理到{" "}
                  <code className="text-foreground">
                    API_PROXY_TARGET / SERVER_PORT
                  </code>
                  （默认 8000）。生产由 nginx 反代，响应信封为{" "}
                  <code className="text-foreground">
                    {"{ code, message, data }"}
                  </code>
                  。
                </p>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">GET /api/v1/site-config</Badge>
                  <Badge variant="secondary">POST /api/v1/auth/login</Badge>
                  <Badge variant="secondary">GET /api/v1/problems</Badge>
                  <Badge variant="secondary">POST /api/v1/submissions</Badge>
                </div>
              </TabsContent>
              <TabsContent value="ui" className="pt-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground">
                      已安装（24）
                    </p>
                    <p className="text-sm leading-relaxed">
                      button · card · input · label · badge · table · tabs ·
                      dialog · dropdown-menu · select · textarea · checkbox ·
                      switch · separator · skeleton · avatar · tooltip ·
                      breadcrumb · pagination · sonner · spinner · empty · sheet
                      · sidebar
                    </p>
                  </div>
                  <div className="space-y-3">
                    <p className="text-xs font-medium text-muted-foreground">
                      加载态示例
                    </p>
                    <div className="flex items-center gap-3">
                      <Skeleton className="size-9 rounded-full" />
                      <div className="w-full space-y-2">
                        <Skeleton className="h-2.5 w-1/2" />
                        <Skeleton className="h-2.5 w-3/4" />
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Avatar className="size-8">
                        <AvatarFallback className="bg-primary/10 text-xs text-primary">
                          PO
                        </AvatarFallback>
                      </Avatar>
                      <div className="text-xs">
                        <p className="font-medium">PigeonOJ</p>
                        <p className="text-muted-foreground">前端骨架</p>
                      </div>
                    </div>
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        <Card size="sm" className="border-dashed bg-transparent ring-0">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <DatabaseIcon className="size-3.5" />
              本页仅验证脚手架，未接入任何业务数据
            </span>
            <span>
              迁移方案与页面清单见{" "}
              <code className="text-foreground">
                docs/frontend-astro-migration.md
              </code>
            </span>
          </CardContent>
        </Card>
      </div>

      {autoRefresh ? null : (
        <p className="mt-2 text-center text-xs text-muted-foreground">
          自动轮询已关闭（演示状态）
        </p>
      )}
      <Toaster position="top-center" />
    </>
  )
}
