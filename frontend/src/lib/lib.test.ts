import { AxiosError, type AxiosResponse } from 'axios'
import { apiError } from './api'
import { translate } from './i18n'
import { fmtBytes, num } from './format'

const axiosErr = (status: number, data: unknown) => {
  const e = new AxiosError('x', 'ERR', undefined, undefined, { status, data } as AxiosResponse)
  return e
}

describe('apiError', () => {
  it('extracts field errors from the uniform envelope', () => {
    const r = apiError(axiosErr(400, { error: { status: 400, detail: 'Validation failed.', fields: { width: ['must be between 200 and 4000'], email: 'taken' } } }))
    expect(r.fields).toEqual({ width: 'must be between 200 and 4000', email: 'taken' })
    expect(r.message).toBe('must be between 200 and 4000')
  })
  it('uses the detail for non-field errors', () => {
    expect(apiError(axiosErr(403, { error: { status: 403, detail: 'Storage limit reached.' } })).message).toBe('Storage limit reached.')
  })
  it('reports network failures distinctly', () => {
    const e = new AxiosError('Network Error', 'ERR_NETWORK')
    expect(apiError(e).message).toMatch(/Cannot reach the server/)
  })
  it('handles rate limiting and unknown errors', () => {
    expect(apiError(axiosErr(429, {})).message).toMatch(/Too many requests/)
    expect(apiError(new Error('boom')).message).toMatch(/Something went wrong/)
  })
})

describe('i18n', () => {
  it('translates and falls back to English then the key', () => {
    expect(translate('uz', 'nav.pricing')).toBe('Narxlar')
    expect(translate('ru', 'nav.pricing')).toBe('Тарифы')
    expect(translate('uz', 'nonexistent.key')).toBe('nonexistent.key')
  })
})

describe('format', () => {
  it('formats bytes', () => { expect(fmtBytes(512)).toBe('512 B'); expect(fmtBytes(1536)).toBe('1.5 KB'); expect(fmtBytes(5 * 1048576)).toBe('5.0 MB') })
  it('num falls back for non-finite input', () => { expect(num('12')).toBe(12); expect(num('x', 7)).toBe(7); expect(num(Infinity, 3)).toBe(3) })
})
