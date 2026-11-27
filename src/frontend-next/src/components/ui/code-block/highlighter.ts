import type { GrammarState, HighlighterCore } from "shiki/core"
import { createHighlighterCore } from "shiki/core"
import { createJavaScriptRegexEngine } from "shiki/engine/javascript"

export interface HighlightedToken {
  content: string
  htmlStyle?: Record<string, string>
}

export interface Highlighter {
  /** Tokenizes code, optionally continuing from a previous grammar state. */
  highlight: (
    code: string,
    state?: GrammarState,
  ) => { lines: HighlightedToken[][], state: GrammarState | undefined }
}

// Add the languages you need. Each one loads the first time it is used.
const languages = {
  bash: () => import("shiki/langs/shellscript.mjs"),
  cpp: () => import("shiki/langs/cpp.mjs"),
  css: () => import("shiki/langs/css.mjs"),
  diff: () => import("shiki/langs/diff.mjs"),
  html: () => import("shiki/langs/html.mjs"),
  java: () => import("shiki/langs/java.mjs"),
  javascript: () => import("shiki/langs/javascript.mjs"),
  json: () => import("shiki/langs/json.mjs"),
  jsx: () => import("shiki/langs/jsx.mjs"),
  markdown: () => import("shiki/langs/markdown.mjs"),
  python: () => import("shiki/langs/python.mjs"),
  sql: () => import("shiki/langs/sql.mjs"),
  tsx: () => import("shiki/langs/tsx.mjs"),
  typescript: () => import("shiki/langs/typescript.mjs"),
  vue: () => import("shiki/langs/vue.mjs"),
  yaml: () => import("shiki/langs/yaml.mjs"),
}

const aliases: Record<string, keyof typeof languages> = {
  "c++": "cpp",
  cpp17: "cpp",
  cxx: "cpp",
  java21: "java",
  js: "javascript",
  md: "markdown",
  py: "python",
  "python3.12": "python",
  python3: "python",
  py3: "python",
  sh: "bash",
  shell: "bash",
  shellscript: "bash",
  ts: "typescript",
  yml: "yaml",
  zsh: "bash",
}

let highlighter: Promise<HighlighterCore> | undefined

function getHighlighter() {
  highlighter ??= createHighlighterCore({
    themes: [
      import("shiki/themes/github-light.mjs"),
      import("shiki/themes/github-dark.mjs"),
    ],
    langs: [],
    engine: createJavaScriptRegexEngine({ forgiving: true }),
  }).catch((error) => {
    highlighter = undefined
    throw error
  })

  return highlighter
}

function getLanguage(language: string) {
  const name = language.toLowerCase()

  if (name === "ansi")
    return name

  if (name in languages)
    return name as keyof typeof languages

  return aliases[name] ?? null
}

// Loads a language and returns a highlighter for it, or null for a language
// that is not listed.
const languageLoads = new Map<string, Promise<Highlighter | null>>()

function createHighlighter(lang: keyof typeof languages | "ansi"): Promise<Highlighter> {
  return getHighlighter().then(async (shiki) => {
    if (lang !== "ansi" && !shiki.getLoadedLanguages().includes(lang))
      await shiki.loadLanguage(languages[lang])

    return {
      // Returns the tokens of each line, and the grammar state after the last
      // line. Pass that state back to continue where the code left off.
      highlight(code: string, state?: GrammarState) {
        const tokenize = (text: string) =>
          shiki.codeToTokens(text, {
            lang,
            themes: { light: "github-light", dark: "github-dark" },
            defaultColor: false,
            grammarState: state,
          }).tokens

        // ANSI has no grammar state, so each line is tokenized on its own and
        // gets the same colors whether it arrives in one piece or streams.
        const tokens = lang === "ansi"
          ? code.split("\n").flatMap(line => tokenize(line))
          : tokenize(code)

        return {
          lines: tokens.map(line =>
            line.map((token): HighlightedToken => ({
              content: token.content,
              htmlStyle: token.htmlStyle as Record<string, string> | undefined,
            })),
          ),
          state: shiki.getLastGrammarState(tokens),
        }
      },
    }
  })
}

export function loadHighlighter(language: string): Promise<Highlighter | null> {
  const lang = getLanguage(language)

  if (!lang)
    return Promise.resolve(null)

  const cached = languageLoads.get(lang)
  if (cached)
    return cached

  const load = createHighlighter(lang).catch((error) => {
    languageLoads.delete(lang)
    throw error
  })
  languageLoads.set(lang, load)

  return load
}

/**
 * Warms up the highlighter ahead of the first code block so syntax colors are
 * already available when the page renders.
 */
export function preloadCodeHighlighting(
  languages: readonly string[] = ["cpp", "python", "java"],
): void {
  for (const language of languages)
    void loadHighlighter(language).catch(() => {})
}


// Returns the tokens of each line, or null for a language that is not listed.
export async function highlightCode(code: string, language: string) {
  const highlighter = await loadHighlighter(language)

  return highlighter ? highlighter.highlight(code).lines : null
}
