// 竞赛向代码补全：为 C++17 / Python3.12 / Java21 提供常用关键字、标准库 API 与成员方法补全。
// 通过 monaco.languages.registerCompletionItemProvider 注册，纯前端、零新依赖。
//
// 两档能力：
//  1) 关键字 / 标准库 API / 文档词：基于词典 + 文档扫描（规避 monaco #2646 关闭内置词补全问题）。
//  2) 成员方法（a. ）：声明扫描式类型推断。用正则扫当前文件里的 `Type name` 声明，建一张
//     「变量名 -> 容器类型」映射；输入 `a.` 时按 a 的实际类型只弹对应方法表，未知类型回退全部方法。
import * as monaco from 'monaco-editor'

type LangKey = 'cpp' | 'python' | 'java'

type EntryKind =
  | 'keyword'
  | 'class'
  | 'function'
  | 'module'
  | 'method'
  | 'constant'

interface CompletionEntry {
  label: string
  kind: EntryKind
  detail?: string
  documentation?: string
}

const KIND_MAP: Record<EntryKind, monaco.languages.CompletionItemKind> = {
  keyword: monaco.languages.CompletionItemKind.Keyword,
  class: monaco.languages.CompletionItemKind.Class,
  function: monaco.languages.CompletionItemKind.Function,
  module: monaco.languages.CompletionItemKind.Module,
  method: monaco.languages.CompletionItemKind.Method,
  constant: monaco.languages.CompletionItemKind.Constant,
}

// ---------------------------------------------------------------------------
// C++17
// ---------------------------------------------------------------------------
const cppCompletions: CompletionEntry[] = [
  // 关键字
  ...[
    'int', 'long long', 'unsigned', 'short', 'char', 'bool', 'float', 'double',
    'void', 'auto', 'const', 'constexpr', 'static', 'struct', 'class', 'enum',
    'union', 'typedef', 'namespace', 'using', 'template', 'typename', 'public',
    'private', 'protected', 'virtual', 'override', 'if', 'else', 'for', 'while',
    'do', 'switch', 'case', 'default', 'break', 'continue', 'return', 'goto',
    'try', 'catch', 'throw', 'new', 'delete', 'sizeof', 'this', 'true', 'false',
    'nullptr', 'inline', 'extern', 'mutable', 'explicit', 'operator', 'friend',
  ].map<CompletionEntry>((label) => ({ label, kind: 'keyword' })),

  // 容器 / 类型
  ...[
    'vector', 'string', 'pair', 'tuple', 'map', 'set', 'multimap', 'multiset',
    'unordered_map', 'unordered_set', 'queue', 'deque', 'stack', 'priority_queue',
    'list', 'array', 'bitset',
  ].map<CompletionEntry>((label) => ({ label, kind: 'class', detail: 'STL container' })),

  // 算法 / 函数
  ...[
    'sort', 'reverse', 'unique', 'lower_bound', 'upper_bound', 'binary_search',
    'next_permutation', 'prev_permutation', 'max', 'min', 'swap', 'abs', 'gcd',
    'lcm', 'accumulate', 'count', 'find', 'fill', 'is_sorted', 'make_pair', 'tie',
    'to_string', 'stoi', 'stoll', 'printf', 'scanf', 'setprecision', 'sync_with_stdio', 'cin.tie', 'cout.tie',
  ].map<CompletionEntry>((label) => ({ label, kind: 'function', detail: 'C++ stdlib' })),

  // 流 / 常量
  { label: 'cout', kind: 'function', detail: 'standard output' },
  { label: 'cin', kind: 'function', detail: 'standard input' },
  { label: 'endl', kind: 'constant', detail: 'newline + flush' },
  { label: 'fixed', kind: 'constant' },
  { label: 'INT_MAX', kind: 'constant', detail: 'max int' },
  { label: 'INT_MIN', kind: 'constant', detail: 'min int' },
  { label: 'LLONG_MAX', kind: 'constant', detail: 'max long long' },

  // 常用成员
  ...[
    'push_back', 'emplace_back', 'size', 'empty', 'clear', 'begin', 'end',
    'front', 'back', 'insert', 'erase', 'substr', 'length',
  ].map<CompletionEntry>((label) => ({ label, kind: 'method', detail: 'STL member' })),
]

// ---------------------------------------------------------------------------
// Python 3.12
// ---------------------------------------------------------------------------
const pythonCompletions: CompletionEntry[] = [
  ...[
    'def', 'class', 'return', 'if', 'elif', 'else', 'for', 'while', 'break',
    'continue', 'pass', 'import', 'from', 'as', 'with', 'try', 'except',
    'finally', 'raise', 'lambda', 'yield', 'global', 'nonlocal', 'assert',
    'del', 'in', 'is', 'not', 'and', 'or', 'None', 'True', 'False', 'async',
    'await', 'match', 'case',
  ].map<CompletionEntry>((label) => ({ label, kind: 'keyword' })),

  ...[
    'print', 'input', 'len', 'range', 'int', 'float', 'str', 'bool', 'list',
    'dict', 'set', 'tuple', 'sorted', 'min', 'max', 'sum', 'abs', 'round',
    'pow', 'divmod', 'enumerate', 'zip', 'map', 'filter', 'reversed', 'all',
    'any', 'ord', 'chr', 'bin', 'hex', 'oct', 'open', 'type', 'isinstance',
    'format', 'frozenset', 'complex', 'bytes', 'bytearray',
  ].map<CompletionEntry>((label) => ({ label, kind: 'function', detail: 'Python builtin' })),

  ...[
    'append', 'extend', 'insert', 'remove', 'pop', 'index', 'count', 'sort',
    'reverse', 'copy', 'split', 'join', 'strip', 'replace', 'find', 'lower',
    'upper', 'startswith', 'endswith', 'isdigit', 'keys', 'values', 'items',
    'get', 'update', 'setdefault',
  ].map<CompletionEntry>((label) => ({ label, kind: 'method', detail: 'object method' })),

  ...[
    'sys', 'collections', 'Counter', 'defaultdict', 'deque', 'heapq', 'bisect',
    'math', 'itertools', 'permutations', 'combinations', 'product', 'accumulate',
    'array', 'random',
  ].map<CompletionEntry>((label) => ({ label, kind: 'module' })),
]

// ---------------------------------------------------------------------------
// Java 21
// ---------------------------------------------------------------------------
const javaCompletions: CompletionEntry[] = [
  ...[
    'public', 'private', 'protected', 'static', 'final', 'class', 'interface',
    'enum', 'void', 'int', 'long', 'double', 'float', 'char', 'boolean', 'byte',
    'short', 'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'default',
    'break', 'continue', 'return', 'new', 'this', 'super', 'try', 'catch',
    'finally', 'throw', 'throws', 'import', 'package', 'extends', 'implements',
    'abstract', 'synchronized', 'volatile', 'transient', 'instanceof', 'null',
    'true', 'false',
  ].map<CompletionEntry>((label) => ({ label, kind: 'keyword' })),

  ...[
    'System', 'Scanner', 'BufferedReader', 'InputStreamReader', 'String',
    'StringBuilder', 'StringBuffer', 'ArrayList', 'LinkedList', 'HashMap',
    'HashSet', 'TreeMap', 'TreeSet', 'PriorityQueue', 'ArrayDeque', 'Stack',
    'Arrays', 'Collections', 'Math', 'Integer', 'Long', 'Double',
    'StringTokenizer',
  ].map<CompletionEntry>((label) => ({ label, kind: 'class' })),

  ...[
    'println', 'print', 'printf', 'nextInt', 'nextLong', 'nextDouble', 'next',
    'nextLine', 'hasNext', 'charAt', 'length', 'substring', 'toCharArray',
    'split', 'indexOf', 'equals', 'compareTo', 'valueOf', 'trim', 'sort', 'fill',
    'binarySearch', 'reverse', 'append', 'add', 'get', 'set', 'remove',
    'contains', 'push', 'pop', 'peek', 'offer', 'poll', 'parseInt', 'parseLong',
    'abs', 'max', 'min', 'pow', 'sqrt',
  ].map<CompletionEntry>((label) => ({ label, kind: 'method', detail: 'Java API' })),
]

// ---------------------------------------------------------------------------
// 成员方法表：变量被推断为某容器类型时，a. 只弹这些
// ---------------------------------------------------------------------------
const METHOD_TABLES: Record<LangKey, Record<string, string[]>> = {
  cpp: {
    vector: [
      'push_back', 'emplace_back', 'pop_back', 'size', 'empty', 'clear',
      'begin', 'end', 'rbegin', 'rend', 'front', 'back', 'insert', 'erase',
      'at', 'resize', 'reserve', 'capacity', 'assign', 'data', 'swap',
    ],
    map: [
      'insert', 'erase', 'find', 'count', 'at', 'contains', 'begin', 'end',
      'size', 'empty', 'clear', 'lower_bound', 'upper_bound', 'equal_range', 'swap',
    ],
    unordered_map: [
      'insert', 'erase', 'find', 'count', 'at', 'contains', 'begin', 'end',
      'size', 'empty', 'clear', 'bucket_count', 'load_factor', 'swap',
    ],
    set: [
      'insert', 'erase', 'find', 'count', 'contains', 'begin', 'end',
      'size', 'empty', 'clear', 'lower_bound', 'upper_bound', 'swap',
    ],
    unordered_set: [
      'insert', 'erase', 'find', 'count', 'contains', 'begin', 'end',
      'size', 'empty', 'clear', 'swap',
    ],
    string: [
      'length', 'size', 'substr', 'find', 'rfind', 'replace', 'append',
      'assign', 'compare', 'c_str', 'at', 'front', 'back', 'empty', 'clear',
      'insert', 'erase', 'push_back', 'pop_back', 'starts_with', 'ends_with',
      'data', 'reserve',
    ],
    deque: ['push_back', 'push_front', 'pop_back', 'pop_front', 'front', 'back', 'size', 'empty', 'clear', 'begin', 'end', 'at'],
    list: ['push_back', 'push_front', 'pop_back', 'pop_front', 'front', 'back', 'size', 'empty', 'clear', 'insert', 'erase', 'reverse', 'sort', 'merge', 'unique'],
    queue: ['push', 'pop', 'front', 'back', 'size', 'empty'],
    stack: ['push', 'pop', 'top', 'size', 'empty'],
    priority_queue: ['push', 'pop', 'top', 'size', 'empty'],
    multimap: ['insert', 'erase', 'find', 'count', 'begin', 'end', 'size', 'empty', 'clear', 'equal_range'],
    multiset: ['insert', 'erase', 'find', 'count', 'contains', 'begin', 'end', 'size', 'empty', 'clear', 'lower_bound', 'upper_bound'],
    pair: ['first', 'second'],
    array: ['at', 'size', 'fill', 'front', 'back', 'data', 'empty'],
    bitset: ['set', 'reset', 'test', 'count', 'any', 'all', 'none', 'flip', 'size', 'to_string', 'to_ulong', 'to_ullong'],
  },
  python: {
    list: ['append', 'extend', 'insert', 'remove', 'pop', 'index', 'count', 'sort', 'reverse', 'copy', 'clear'],
    dict: ['keys', 'values', 'items', 'get', 'update', 'setdefault', 'pop', 'popitem', 'clear', 'copy', 'fromkeys'],
    set: ['add', 'remove', 'discard', 'pop', 'clear', 'copy', 'union', 'intersection', 'difference', 'issubset', 'issuperset', 'update'],
    str: [
      'split', 'join', 'strip', 'lstrip', 'rstrip', 'replace', 'find', 'rfind',
      'startswith', 'endswith', 'upper', 'lower', 'capitalize', 'title', 'format',
      'center', 'count', 'isdigit', 'encode', 'partition', 'splitlines', 'zfill',
    ],
    tuple: ['count', 'index'],
    frozenset: ['add', 'remove', 'discard', 'pop', 'clear', 'copy', 'union', 'intersection', 'difference', 'issubset', 'issuperset', 'update'],
  },
  java: {
    ArrayList: ['add', 'get', 'set', 'remove', 'size', 'isEmpty', 'clear', 'contains', 'indexOf', 'lastIndexOf', 'toArray', 'iterator', 'addAll'],
    LinkedList: ['add', 'addFirst', 'addLast', 'get', 'getFirst', 'getLast', 'remove', 'removeFirst', 'removeLast', 'peek', 'poll', 'size', 'isEmpty', 'clear'],
    ArrayDeque: ['addFirst', 'addLast', 'getFirst', 'getLast', 'peekFirst', 'peekLast', 'pollFirst', 'pollLast', 'removeFirst', 'removeLast', 'size', 'isEmpty', 'clear'],
    Stack: ['push', 'pop', 'peek', 'search', 'size', 'isEmpty', 'clear'],
    PriorityQueue: ['add', 'offer', 'remove', 'poll', 'peek', 'element', 'size', 'isEmpty', 'contains', 'clear'],
    HashMap: ['put', 'get', 'remove', 'containsKey', 'containsValue', 'size', 'isEmpty', 'clear', 'keySet', 'values', 'entrySet', 'putIfAbsent', 'getOrDefault'],
    TreeMap: ['put', 'get', 'remove', 'containsKey', 'firstKey', 'lastKey', 'floorKey', 'ceilingKey', 'lowerKey', 'higherKey', 'size', 'isEmpty', 'clear', 'keySet', 'values', 'entrySet'],
    HashSet: ['add', 'remove', 'contains', 'size', 'isEmpty', 'clear', 'iterator'],
    TreeSet: ['add', 'remove', 'contains', 'first', 'last', 'floor', 'ceiling', 'lower', 'higher', 'size', 'isEmpty', 'clear', 'iterator'],
    String: [
      'length', 'charAt', 'substring', 'indexOf', 'lastIndexOf', 'replace', 'split',
      'trim', 'toUpperCase', 'toLowerCase', 'equals', 'compareTo', 'startsWith',
      'endsWith', 'contains', 'valueOf', 'toCharArray', 'isEmpty', 'concat',
    ],
    StringBuilder: ['append', 'insert', 'delete', 'deleteCharAt', 'replace', 'reverse', 'toString', 'length', 'charAt', 'setCharAt', 'substring', 'capacity', 'ensureCapacity', 'indexOf', 'lastIndexOf'],
    StringBuffer: ['append', 'insert', 'delete', 'deleteCharAt', 'replace', 'reverse', 'toString', 'length', 'charAt', 'setCharAt', 'substring', 'capacity', 'ensureCapacity', 'indexOf', 'lastIndexOf'],
    Scanner: ['next', 'nextLine', 'nextInt', 'nextLong', 'nextDouble', 'nextFloat', 'hasNext', 'hasNextInt', 'hasNextLine', 'useDelimiter', 'close'],
  },
}

// 预置接收者：静态字段 / 全局对象（声明扫描无法识别），如 System.out、Math。
// 命中时直接给出对应方法，避免回退成「全部方法」而显示错误列表。
const PRESET_RECEIVERS: Partial<Record<LangKey, Record<string, string[]>>> = {
  java: {
    System: [
      'out', 'err', 'in', 'currentTimeMillis', 'arraycopy', 'exit', 'gc',
      'getProperty', 'setProperty', 'getenv', 'identityHashCode', 'lineSeparator',
    ],
    'System.out': [
      'println', 'print', 'printf', 'format', 'append', 'flush', 'close', 'checkError', 'write',
    ],
    'System.err': [
      'println', 'print', 'printf', 'format', 'append', 'flush', 'close', 'checkError', 'write',
    ],
    Math: [
      'abs', 'max', 'min', 'pow', 'sqrt', 'cbrt', 'floor', 'ceil', 'round', 'random',
      'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'toRadians', 'toDegrees', 'log', 'log10',
      'exp', 'copySign', 'signum', 'hypot', 'nextUp', 'nextDown',
    ],
    Arrays: [
      'sort', 'parallelSort', 'fill', 'binarySearch', 'copyOf', 'copyOfRange', 'equals',
      'deepEquals', 'toString', 'asList', 'stream', 'hashCode',
    ],
    Collections: [
      'sort', 'reverse', 'max', 'min', 'binarySearch', 'frequency', 'shuffle', 'rotate',
      'emptyList', 'singletonList', 'nCopies', 'unmodifiableList', 'disjoint',
    ],
    Integer: ['parseInt', 'parseUnsignedInt', 'toString', 'valueOf', 'max', 'min', 'compare', 'sum', 'toBinaryString', 'toHexString', 'toOctalString', 'highestOneBit', 'lowestOneBit', 'numberOfLeadingZeros', 'numberOfTrailingZeros', 'rotateLeft', 'rotateRight', 'signum', 'reverse', 'reverseBytes', 'bitCount'],
    Long: ['parseLong', 'toString', 'valueOf', 'max', 'min', 'compare', 'sum', 'toBinaryString', 'toHexString', 'toOctalString', 'highestOneBit', 'lowestOneBit', 'numberOfLeadingZeros', 'numberOfTrailingZeros', 'rotateLeft', 'rotateRight', 'signum', 'reverse', 'reverseBytes', 'bitCount'],
    Double: ['parseDouble', 'toString', 'valueOf', 'isNaN', 'isInfinite', 'isFinite', 'max', 'min', 'compare', 'sum', 'longBitsToDouble', 'doubleToLongBits', 'doubleToRawLongBits', 'toHexString', 'POSITIVE_INFINITY', 'NEGATIVE_INFINITY', 'NaN', 'MAX_VALUE', 'MIN_VALUE'],
    Boolean: ['parseBoolean', 'toString', 'valueOf', 'compare', 'logicalAnd', 'logicalOr', 'logicalXor', 'TRUE', 'FALSE'],
    Objects: ['equals', 'deepEquals', 'hashCode', 'hash', 'toString', 'requireNonNull', 'requireNonNullElse', 'isNull', 'nonNull', 'compare'],
    String: ['valueOf', 'format', 'join', 'copyValueOf'],
    List: ['of', 'copyOf', 'range'],
    Map: ['of', 'ofEntries', 'copyOf', 'entry'],
    Set: ['of', 'copyOf'],
  },
}

// ---------------------------------------------------------------------------
// 声明扫描：建「变量名 -> 容器类型」映射
// ---------------------------------------------------------------------------
function baseTypeOf(typeToken: string): string {
  return typeToken.replace(/^std::/, '').split('<')[0].split('::').pop() ?? typeToken
}

function scanCpp(model: monaco.editor.ITextModel): Map<string, string> {
  const text = model.getValue()
  // 先收集 using 别名：using vi = vector<int>;
  const alias = new Map<string, string>()
  const aliasRe = /\busing\s+([A-Za-z_]\w*)\s*=\s*((?:std::)?[A-Za-z_]\w*(?:::\w+)*)\s*(?:<[^;{}()]*>)?\s*;/g
  let am: RegExpExecArray | null
  while ((am = aliasRe.exec(text)) !== null) alias.set(am[1], baseTypeOf(am[2]))
  const known = Object.keys(METHOD_TABLES.cpp)
  const names = Array.from(new Set([...known, ...alias.keys()]))
  const map = new Map<string, string>()
  for (const n of names) {
    const base = alias.get(n) ?? (known.includes(n) ? n : null)
    if (!base) continue
    const re = new RegExp(`\\b(?:std::)?${n}\\b\\s*(?:<[^;{}()]*>)?\\s+([A-Za-z_]\\w*)\\s*(?:=|\\(|\\[|;|\\{)`, 'g')
    let m: RegExpExecArray | null
    while ((m = re.exec(text)) !== null) map.set(m[1], base)
  }
  return map
}

function scanPython(model: monaco.editor.ITextModel): Map<string, string> {
  const text = model.getValue()
  const map = new Map<string, string>()
  const known = ['list', 'dict', 'set', 'str', 'tuple']
  const push = (name: string, type: string) => map.set(name, type)
  let m: RegExpExecArray | null
  const reAssign = new RegExp(`\\b([A-Za-z_]\\w*)\\s*=\\s*(${known.join('|')})\\s*\\(`, 'g')
  while ((m = reAssign.exec(text)) !== null) push(m[1], m[2])
  const reAnno = new RegExp(`\\b([A-Za-z_]\\w*)\\s*:\\s*(${known.join('|')})\\b`, 'g')
  while ((m = reAnno.exec(text)) !== null) push(m[1], m[2])
  const reList = /\b([A-Za-z_]\w*)\s*=\s*\[\]/g
  while ((m = reList.exec(text)) !== null) push(m[1], 'list')
  const reDict = /\b([A-Za-z_]\w*)\s*=\s*\{\}/g
  while ((m = reDict.exec(text)) !== null) push(m[1], 'dict')
  return map
}

function scanJava(model: monaco.editor.ITextModel): Map<string, string> {
  const text = model.getValue()
  const map = new Map<string, string>()
  const modifiers = '(?:private |protected |public |static |final |volatile |transient |synchronized )*'
  for (const type of Object.keys(METHOD_TABLES.java)) {
    const re = new RegExp(`\\b${modifiers}(?:[A-Za-z_][\\w.]*)?\\s*${type}\\s*(?:<[^;{}()]*>)?\\s+([A-Za-z_]\\w*)\\s*(?:=|;)`, 'g')
    let m: RegExpExecArray | null
    while ((m = re.exec(text)) !== null) map.set(m[1], type)
  }
  return map
}

const SCANNERS: Record<LangKey, (model: monaco.editor.ITextModel) => Map<string, string>> = {
  cpp: scanCpp,
  python: scanPython,
  java: scanJava,
}

// 基于当前文档收集词，作为补全项（规避 #2646）。
// exclude 为已存在的词典标签，避免「关键字/API」与「文档词」重复出现。
function buildWordSuggestions(
  model: monaco.editor.ITextModel,
  range: monaco.IRange,
  exclude: Set<string>,
): monaco.languages.CompletionItem[] {
  const text = model.getValue()
  const seen = new Set<string>()
  const re = /[A-Za-z_][A-Za-z0-9_]*/g
  let match: RegExpExecArray | null
  while ((match = re.exec(text)) !== null) {
    if (match[0].length >= 3) seen.add(match[0])
  }
  return Array.from(seen)
    .slice(0, 400)
    .filter((word) => !exclude.has(word))
    .map((word) => ({
      label: word,
      kind: monaco.languages.CompletionItemKind.Text,
      insertText: word,
      range,
      sortText: '2' + word,
    }))
}

function makeProvider(lang: LangKey, entries: CompletionEntry[]): monaco.languages.CompletionItemProvider {
  // 预计算词典标签，供文档词去重
  const curatedLabels = new Set(entries.map((e) => e.label))
  return {
    triggerCharacters: ['.'],
    provideCompletionItems(model, position) {
      const linePrefix = model.getValueInRange({
        startLineNumber: position.lineNumber,
        startColumn: 1,
        endLineNumber: position.lineNumber,
        endColumn: position.column,
      })
      // 成员访问：a. 或 a.part（支持多级链 System.out.）
      const member = /([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\.\s*(\w*)$/.exec(linePrefix)
      if (member) {
        const receiver = member[1]
        const partial = member[2]
        const range: monaco.IRange = {
          startLineNumber: position.lineNumber,
          startColumn: position.column - partial.length,
          endLineNumber: position.lineNumber,
          endColumn: position.column,
        }
        // 预置接收者：System.out / Math / Arrays / Collections 等
        const preset = PRESET_RECEIVERS[lang]?.[receiver]
        if (preset) {
          const suggestions = preset.map((m) => ({
            label: m,
            kind: monaco.languages.CompletionItemKind.Method,
            insertText: m,
            range,
            sortText: '0' + m,
            detail: receiver,
          }))
          return { suggestions }
        }
        // 普通局部变量：声明扫描推断类型。推断不到则不要乱弹（避免 System. 等无关列表）
        const typeMap = SCANNERS[lang](model)
        const typeName = receiver.split('.').length === 1 ? typeMap.get(receiver) : undefined
        const methodList = typeName ? METHOD_TABLES[lang][typeName] : undefined
        if (!methodList) return { suggestions: [] }
        const suggestions = methodList.map((m) => ({
          label: m,
          kind: monaco.languages.CompletionItemKind.Method,
          insertText: m,
          range,
          sortText: '0' + m,
          detail: typeName,
        }))
        return { suggestions }
      }

      // 常规路径：关键字 / 标准库 API / 文档词
      const word = model.getWordUntilPosition(position)
      const range: monaco.IRange = {
        startLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endLineNumber: position.lineNumber,
        endColumn: word.endColumn,
      }
      const suggestions: monaco.languages.CompletionItem[] = entries.map((entry) => ({
        label: entry.label,
        kind: KIND_MAP[entry.kind],
        detail: entry.detail,
        documentation: entry.documentation,
        insertText: entry.label,
        range,
        sortText: '0' + entry.label,
      }))
      return { suggestions: [...suggestions, ...buildWordSuggestions(model, range, curatedLabels)] }
    },
  }
}

// dev HMR 会重新执行本模块，若仅用布尔守卫，旧的 provider 不会被注销而持续累积，
// 导致同一条建议重复出现多次。故把 disposable 存到 globalThis，每次注册前先全部 dispose。
const DISPOSE_KEY = '__pigeon_completion_disposables__'
const globalRef = globalThis as unknown as Record<string, monaco.IDisposable[] | undefined>
const disposables: monaco.IDisposable[] = globalRef[DISPOSE_KEY] ?? []
globalRef[DISPOSE_KEY] = disposables

export function registerProblemCompletions(): void {
  for (const d of disposables) d.dispose()
  disposables.length = 0
  disposables.push(
    monaco.languages.registerCompletionItemProvider('cpp', makeProvider('cpp', cppCompletions)),
    monaco.languages.registerCompletionItemProvider('python', makeProvider('python', pythonCompletions)),
    monaco.languages.registerCompletionItemProvider('java', makeProvider('java', javaCompletions)),
  )
}
