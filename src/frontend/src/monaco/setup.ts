// Monaco 按需入口（性能优化）：替代 `import * as monaco from 'monaco-editor'` 全量入口。
//
// 全量入口 = editor.all（全部编辑器特性）+ 全部 basic-languages（90+ 语言 Monarch）
// + css/html/json/typescript 语言服务及其 worker，产物 3MB+。
// 本项目只需 C++ / Python / Java 三种语言的语法高亮（Monarch，主线程运行）：
// - editor.all.js：全部编辑器特性（补全建议框、括号匹配、查找等），无语言；
// - cpp / python / java 的 basic-languages contribution：按需注册三种语言；
// - editor.api.js：monaco 对象（editor / languages 命名空间，含 TS 类型）。
// 语言服务 worker 只需 editorWorker（补全等特性依赖），不再引入 ts/css/json worker。
//
// 使用方统一 `import * as monaco from '@/monaco/setup'`；主题见 theme.ts，补全见 completions.ts。
import 'monaco-editor/esm/vs/editor/editor.all.js'
// OJ 支持语言（docs/architecture.md：Python 3.12 / C++17 / Java 21）的 Monarch 高亮
import 'monaco-editor/esm/vs/basic-languages/cpp/cpp.contribution'
import 'monaco-editor/esm/vs/basic-languages/python/python.contribution'
import 'monaco-editor/esm/vs/basic-languages/java/java.contribution'
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import 'monaco-editor/esm/vs/editor/editor.api'

// 未配置 getWorker 时 monaco 运行期报错并降级（词法建议 / 链接检测失效）
self.MonacoEnvironment = {
  getWorker() {
    return new EditorWorker()
  },
}

export * from 'monaco-editor/esm/vs/editor/editor.api'
