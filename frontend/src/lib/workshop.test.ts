import { buildPrices, emptyPriceForm, hasAnyPrice, parseAmount } from './workshop'
import { fmtMoney, fromLocalInput, toLocalInput } from './format'

describe('parseAmount', () => {
  it('reads plain numbers, decimal commas and spaced thousands', () => {
    expect(parseAmount('95000')).toBe(95000); expect(parseAmount('12,5')).toBe(12.5); expect(parseAmount(' 1 250 000 ')).toBe(1250000); expect(parseAmount('0')).toBe(0)
  })
  it('treats empty, negative and non-numeric input as "not provided"', () => {
    for (const bad of ['', '   ', 'abc', '-5', '1e', 'NaN', 'Infinity']) expect(parseAmount(bad)).toBeNull()
  })
})

describe('buildPrices', () => {
  it('leaves empty fields out entirely so the server reports them as missing instead of pricing them at zero', () => {
    const f = { ...emptyPriceForm(), board: { 'MDF 18': '100', HDF: '' }, hardware: { Hinge: '5', Handle: 'x' }, edge: '', labor: '2' }
    expect(buildPrices(f)).toEqual({ currency: '', board_price_per_m2: { 'MDF 18': 100 }, hardware_prices: { Hinge: 5 }, labor_per_m2: 2, waste_factor: 0.15 })
  })
  it('keeps an explicit zero price, converts percentages and caps them like the server does', () => {
    const out = buildPrices({ ...emptyPriceForm(), board: { MDF: '0' }, waste: '80', markup: '500', currency: ' UZS ' })
    expect(out.board_price_per_m2).toEqual({ MDF: 0 }); expect(out.waste_factor).toBe(0.6); expect(out.markup_pct).toBe(300); expect(out.currency).toBe('UZS')
  })
  it('hasAnyPrice is false for an untouched form (waste and markup alone are not prices)', () => {
    expect(hasAnyPrice(emptyPriceForm())).toBe(false)
    expect(hasAnyPrice({ ...emptyPriceForm(), markup: '10', waste: '20' })).toBe(false)
    expect(hasAnyPrice({ ...emptyPriceForm(), hardware: { Hinge: '3' } })).toBe(true)
    expect(hasAnyPrice({ ...emptyPriceForm(), labor: '0' })).toBe(true)
  })
})

describe('formatting', () => {
  it('fmtMoney shows decimals only when needed and dashes for missing values', () => {
    expect(fmtMoney('12000000')).toBe((12000000).toLocaleString()); expect(fmtMoney('749.5')).toBe((749.5).toLocaleString(undefined, { minimumFractionDigits: 2 }))
    expect(fmtMoney(null)).toBe('-'); expect(fmtMoney('')).toBe('-'); expect(fmtMoney('abc')).toBe('-'); expect(fmtMoney(5, 'UZS')).toBe('5 UZS')
  })
  it('datetime-local round-trips through ISO without drifting', () => {
    const local = '2026-12-05T17:30'
    expect(toLocalInput(fromLocalInput(local))).toBe(local); expect(fromLocalInput('')).toBeNull(); expect(toLocalInput(null)).toBe('')
  })
})
