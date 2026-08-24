import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'

export default defineConfigWithVueTs(
  {
    name: 'app/files-to-lint',
    files: ['**/*.{ts,vue}'],
    languageOptions: {
      globals: {
        ...globals.browser,
      },
    },
  },

  pluginVue.configs['flat/essential'],
  vueTsConfigs.recommended,

  // 格式类规则交给 Prettier（.prettierrc.json），避免双工具冲突
  skipFormatting,
  {
    name: 'app/project-rules',
    rules: {
      // App.vue 为框架约定的单词组件名
      'vue/multi-word-component-names': 'off',
      // 题面等 Markdown 富文本经 markdown-it(html:false) + DOMPurify 白名单过滤后渲染（docs/frontend.md）
      'vue/no-v-html': 'off',
      // 存量代码含 any（i18n 字典、第三方类型兜底），专项清理后再开启
      '@typescript-eslint/no-explicit-any': 'off',
      // 下划线前缀 = 有意保留的未用变量（如仅用于类型推断的参数）
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
    },
  },
  {
    name: 'app/ignores',
    ignores: ['dist/**', 'node_modules/**', 'coverage/**', 'node_modules/.vite-config/**'],
  },
)
