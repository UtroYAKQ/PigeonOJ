import { beforeEach, describe, expect, it, vi } from 'vitest'

import { downloadCsv } from './csv'

/** 捕获传给 Blob 的内容与触发下载的文件名 */
function captureDownload() {
  const anchor = { href: '', download: '', click: vi.fn() }
  const createElement = vi
    .spyOn(document, 'createElement')
    .mockReturnValue(anchor as unknown as HTMLAnchorElement)
  // jsdom 未实现 URL.createObjectURL / revokeObjectURL，注入替身
  const createObjectURL = vi.fn(() => 'blob:mock')
  const revokeObjectURL = vi.fn()
  Object.defineProperty(URL, 'createObjectURL', {
    value: createObjectURL,
    configurable: true,
    writable: true,
  })
  Object.defineProperty(URL, 'revokeObjectURL', {
    value: revokeObjectURL,
    configurable: true,
    writable: true,
  })

  let content = ''
  class FakeBlob {
    constructor(parts: BlobPart[]) {
      content = parts.map((p) => (typeof p === 'string' ? p : '')).join('')
    }
  }
  vi.stubGlobal('Blob', FakeBlob)
  return {
    anchor,
    createElement,
    createObjectURL,
    revokeObjectURL,
    text: () => content,
  }
}

describe('downloadCsv', () => {
  let captured: ReturnType<typeof captureDownload>

  beforeEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    captured = captureDownload()
  })

  it('生成含 BOM 的 CSV 并触发下载', () => {
    downloadCsv('users.csv', ['id', 'name'], [[1, '鸽']])
    expect(captured.anchor.download).toBe('users.csv')
    expect(captured.anchor.click).toHaveBeenCalledOnce()
    expect(captured.revokeObjectURL).toHaveBeenCalledWith('blob:mock')

    const text = captured.text()
    expect(text.charCodeAt(0)).toBe(0xfeff) // UTF-8 BOM，保证 Excel 打开不乱码
    expect(text.slice(1)).toBe('id,name\n1,鸽')
  })

  it('包含逗号 / 引号 / 换行的字段按 RFC 4180 转义', () => {
    downloadCsv('logs.csv', ['path'], [['/api/v1/a,b'], ['say "hi"'], ['line1\nline2']])
    expect(captured.text()).toBe('\uFEFFpath\n"/api/v1/a,b"\n"say ""hi"""\n"line1\nline2"')
  })

  it('null / undefined 字段输出空串', () => {
    downloadCsv('x.csv', ['a', 'b'], [[null, undefined]])
    expect(captured.text()).toBe('\uFEFFa,b\n,')
  })
})
