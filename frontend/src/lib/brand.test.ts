/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8')

const theme = (name: string) => {
  const block = css.match(new RegExp(`${name}\\s*\\{([^}]*)\\}`))![1]
  return Object.fromEntries([...block.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]]))
}
const lum = (hex: string) => { const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2] }
const ratio = (a: string, b: string) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05) }

describe('contrast helper', () => {
  it('matches the WCAG reference values (so the checks below are not vacuous)', () => {
    expect(ratio('#ffffff', '#000000')).toBeCloseTo(21, 1); expect(ratio('#777777', '#ffffff')).toBeCloseTo(4.48, 1); expect(ratio('#22d3ee', '#ffffff')).toBeLessThan(2)
  })
})

describe('brand colours (Deep Navy #0F172A, Cyan #22D3EE, White)', () => {
  const dark = theme(':root, \\[data-theme="dark"\\]'), light = theme('\\[data-theme="light"\\]')
  it('uses the brand palette in the dark theme', () => {
    expect(dark.bg.toLowerCase()).toBe('#0f172a'); expect(dark.primary.toLowerCase()).toBe('#22d3ee'); expect(dark.fg.toLowerCase()).toBe('#ffffff')
  })
  for (const [name, t] of [['dark', dark], ['light', light]] as const) {
    it(`${name}: text and controls reach WCAG AA contrast (4.5:1)`, () => {
      const pairs: [string, string][] = [['fg', 'bg'], ['fg', 'card'], ['muted', 'bg'], ['muted', 'card'], ['on-primary', 'primary'], ['primary', 'bg'], ['primary', 'card']]
      for (const [a, b] of pairs) expect(ratio(t[a], t[b]), `${name} ${a} on ${b}`).toBeGreaterThanOrEqual(4.5)
    })
    it(`${name}: status colours are readable on cards (3:1 for icons/large text)`, () => {
      for (const c of ['success', 'warning', 'danger']) expect(ratio(t[c], t.card), `${name} ${c}`).toBeGreaterThanOrEqual(3)
    })
  }
})
