import { describe, expect, it } from 'vitest'
import { dictionaries } from './i18n'

describe('translation dictionaries', () => {
  const enKeys = Object.keys(dictionaries.en)
  for (const lang of ['uz', 'ru'] as const) {
    it(`${lang} has every English key`, () => {
      expect(enKeys.filter((k) => !(k in dictionaries[lang]))).toEqual([])
    })
    it(`${lang} has no keys missing from English`, () => {
      expect(Object.keys(dictionaries[lang]).filter((k) => !(k in dictionaries.en))).toEqual([])
    })
    it(`${lang} has no empty values`, () => {
      expect(Object.entries(dictionaries[lang]).filter(([, v]) => !v.trim())).toEqual([])
    })
  }
  it('keeps the {n} placeholder in every language', () => {
    for (const l of ['en', 'uz', 'ru'] as const) expect(dictionaries[l]['calc.waste']).toContain('{n}')
  })
})
