import { dictionaries } from './i18n'
import { ORDER_STATUSES, PAYMENT_STATUSES, TASK_PRIORITIES, TASK_STATUSES } from './workshop'

const sources = import.meta.glob(['../**/*.tsx', '!../**/*.test.tsx'], { query: '?raw', import: 'default', eager: true }) as Record<string, string>

describe('every translation key used in the UI exists', () => {
  const used = new Set<string>()
  for (const src of Object.values(sources)) for (const m of src.matchAll(/\bt\('([^']+)'\)/g)) used.add(m[1])
  it('finds the literal t("...") keys in the source', () => { expect(used.size).toBeGreaterThan(150) })
  for (const lang of ['en', 'uz', 'ru'] as const) {
    it(`${lang} defines every literal key`, () => { expect([...used].filter((k) => !(k in dictionaries[lang]))).toEqual([]) })
  }
  it('defines the dynamic key families in all languages', () => {
    const fam: string[] = [
      ...ORDER_STATUSES.map((s) => `order.st.${s}`), ...PAYMENT_STATUSES.map((s) => `pay.${s}`), ...TASK_STATUSES.map((s) => `task.st.${s}`), ...TASK_PRIORITIES.map((s) => `task.pr.${s}`),
      ...['active', 'inactive', 'suspended'].map((s) => `ws.st.${s}`), ...['owner', 'employee'].map((s) => `role.${s}`), ...['active', 'invited', 'removed'].map((s) => `mstatus.${s}`),
      ...['remove', 'leave', 'transfer'].flatMap((k) => [`team.${k}Title`, `team.${k}Do`]), ...['standard', 'kitchen_base', 'kitchen_wall', 'sliding_wardrobe'].map((s) => `type.${s}`),
      ...['kitchen_base', 'kitchen_wall', 'sliding_wardrobe'].map((s) => `type.${s}.hint`), ...['board', 'edge_banding', 'hardware', 'labor'].map((s) => `price.cat.${s}`),
      ...['perspective', 'front', 'side', 'top'].map((s) => `ed.view.${s}`), ...['carcass', 'fronts', 'back', 'handle'].map((s) => `ed.group.${s}`), ...['carcass', 'shelf', 'door', 'drawer', 'back', 'handle'].map((s) => `ed.kind.${s}`),
      ...['bar', 'knob', 'none'].map((s) => `ed.handle.${s}`),
    ]
    for (const lang of ['en', 'uz', 'ru'] as const) expect(fam.filter((k) => !(k in dictionaries[lang]))).toEqual([])
  })
  it('keeps {n}/{name} placeholders in every language', () => {
    for (const [k, v] of Object.entries(dictionaries.en)) for (const ph of v.match(/\{[a-z]+\}/g) ?? []) for (const lang of ['uz', 'ru'] as const) expect(dictionaries[lang][k], `${lang} ${k}`).toContain(ph)
  })
})
