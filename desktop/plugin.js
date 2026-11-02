/**
 * SURP marketplace desktop page — live Surplus Intelligence market data with
 * the plugin's full routing toolkit, presented visually.
 *
 * What this page does:
 * - Markets view: every model's live best price, seller count and volume;
 *   drill into any model for its full order book (per-offer price, capacity,
 *   health, provider).
 * - Providers view: each provider's trusted flag plus live TPS (p50), TTFT,
 *   latency and uptime. Filter to trusted only in one tap.
 * - Router view: the same preferences the surp_route_prefs tool owns —
 *   trusted-only, block/prefer, objective, secret masking — stored per
 *   profile and shared with the agent.
 * - Composer actions: Fast TPS and Cheapest 5 sit immediately before the model
 *   pill, follow its selected model, and edit the same shared route preferences.
 * - Default route: pick the combo the agent uses first (kept in plugin
 *   storage; the surp skill reads it before choosing a route).
 *
 * What this page NEVER does: send a paid request. "Draft in chat" writes a
 * reviewed request into the chat composer; the agent's surp_chat tool (plus
 * the pre_tool_call spend-approval gate) applies the same protections as a
 * typed request, and the user always approves the spend.
 *
 * Plain ESM, loaded uncompiled — UI is jsx() calls, not JSX syntax.
 * Only these imports resolve: @hermes/plugin-sdk, react, react/jsx-runtime.
 */

import { cn, host, haptic, useValue, Tip, SearchField, Button, Switch, Badge, SegmentedControl, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Popover, PopoverContent, PopoverTrigger, GlyphSpinner, EmptyState, ErrorState, PANES_AREA, ROUTES_AREA, SIDEBAR_NAV_AREA, PALETTE_AREA, COMPOSER_AREAS } from '@hermes/plugin-sdk'
import React, { useState, useEffect, useCallback } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'surp-hermes-x402-llm'

const card = { padding: 16, borderRadius: 14, background: 'var(--ui-bg-elevated)', border: '1px solid var(--ui-stroke-secondary)', display: 'grid', gap: 12 }
const main = { padding: 24, maxWidth: 980, boxSizing: 'border-box', color: 'var(--ui-text-primary)', display: 'grid', gap: 20 }
const muted = { fontSize: 12, color: 'var(--ui-text-secondary)', lineHeight: 1.6, margin: 0 }
const field = { display: 'grid', gap: 8, fontSize: 14, color: 'var(--ui-text-secondary)' }
const control = { width: '100%', boxSizing: 'border-box', padding: '10px 12px', borderRadius: 10, border: '1px solid var(--ui-stroke-secondary)', background: 'var(--ui-bg-base)', color: 'var(--ui-text-primary)', minHeight: 42 }
const rowBetween = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }
const table = { width: '100%', borderCollapse: 'collapse', fontSize: 13 }
const cell = { textAlign: 'left', padding: '8px 6px', borderBottom: '1px solid var(--ui-stroke-secondary)', verticalAlign: 'top' }
const num = { ...cell, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }
const composerTrigger = { height: 28, padding: '0 8px', borderRadius: 8, border: '1px solid var(--ui-stroke-secondary)', background: 'transparent', color: 'var(--ui-text-secondary)', cursor: 'pointer', font: 'inherit', fontSize: 13, whiteSpace: 'nowrap' }
const providerRow = { width: '100%', display: 'grid', gridTemplateColumns: 'minmax(110px,1fr) auto', gap: 12, alignItems: 'center', textAlign: 'left', padding: 10, borderRadius: 10, border: '1px solid var(--ui-stroke-secondary)', background: 'transparent', color: 'var(--ui-text-primary)', cursor: 'pointer', font: 'inherit' }

function useSurp(ctx, path, deps) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    if (!path) { setData(null); setError(null); return () => {} }
    let live = true
    setError(null)
    ctx.rest(path).then(
      value => { if (live) setData(value) },
      err => { if (live) setError(String((err && err.message) || err)) }
    )
    return () => { live = false }
  }, deps)
  return [data, error, setData]
}

function usdPer1m(micro) {
  if (micro === null || micro === undefined) return '—'
  const per1m = Number(micro) / 1000000
  if (!Number.isFinite(per1m)) return '—'
  return '$' + per1m.toFixed(4)
}

function MarketsView({ ctx, onUseProvider }) {
  const [query, setQuery] = useState('')
  const [detail, setDetail] = useState(null)
  const [markets, error] = useSurp(ctx, '/markets?limit=500&sort=sellers&dir=desc', [])
  const [book, bookError] = useSurp(ctx, detail ? `/markets/${encodeURIComponent(detail)}` : null, [detail])
  const [performance, performanceError] = useSurp(ctx, detail ? `/performance/${encodeURIComponent(detail)}` : null, [detail])
  if (error) return jsx(ErrorState, { message: error })
  if (!markets) return jsx(GlyphSpinner, {})
  const rows = (markets.models || []).slice().sort((a, b) => (Number(b.seller_count || b.num_sellers || b.healthy_seller_count || 0)) - (Number(a.seller_count || a.num_sellers || a.healthy_seller_count || 0))).filter(r => {
    const id = String(r.model || r.id || '')
    return !query || id.toLowerCase().includes(query.toLowerCase())
  })
  const perfRows = ((performance && performance.providers) || []).slice().sort((a, b) => (Number(b.tps_p50) || 0) - (Number(a.tps_p50) || 0))
  const fastest = perfRows.find(p => p.tps_p50 !== null && Number.isFinite(Number(p.tps_p50)))
  return jsxs('div', { style: { display: 'grid', gap: 16 }, children: [
    jsx('div', { style: rowBetween, children: [
      jsx('p', { style: muted, children: `${markets.count} models · live Surplus Intelligence prices` }),
      jsx(SearchField, { value: query, onChange: setQuery, placeholder: 'Filter models', 'aria-label': 'Filter models' })
    ] }),
    jsx('div', { style: { overflowX: 'auto' }, children: jsx('table', { style: table, children: [
      jsx('thead', { children: jsx('tr', { children: [
        jsx('th', { style: cell, children: 'Model' }),
        jsx('th', { style: num, children: 'Best /1M' }),
        jsx('th', { style: num, children: 'Sellers' }),
        jsx('th', { style: num, children: '24h vol' })
      ] }) }),
      jsx('tbody', { children: rows.slice(0, 100).map(r => {
        const id = String(r.model || r.id || '')
        return jsx('tr', { key: id, children: [
          jsx('td', { style: cell, children: jsx('button', { type: 'button', onClick: () => { haptic('tap'); setDetail(id) }, style: { background: 'none', border: 'none', padding: '8px', color: 'var(--ui-accent)', cursor: 'pointer', font: 'inherit' }, children: id }) }),
          jsx('td', { style: num, children: usdPer1m(r.best_price_per_1m ?? r.best_input_per_1m) }),
          jsx('td', { style: num, children: r.seller_count ?? r.num_sellers ?? r.healthy_seller_count ?? '—' }),
          jsx('td', { style: num, children: r.volume_24h !== undefined && r.volume_24h !== null ? '$' + Number(r.volume_24h).toFixed(0) : '—' })
        ] })
      }) })
    ] }) }),
    detail ? jsxs('div', { style: card, children: [
      jsx('div', { style: rowBetween, children: [
        jsx('h2', { style: { fontSize: 16, margin: 0 }, children: detail }),
        jsx('button', { type: 'button', onClick: () => setDetail(null), style: { ...control, width: 'auto', minHeight: 0, padding: '6px 10px', cursor: 'pointer' }, children: 'Close' })
      ] }),
      performanceError ? jsx(ErrorState, { message: performanceError }) : !performance ? jsx(GlyphSpinner, {}) : jsxs('div', { style: { display: 'grid', gap: 10 }, children: [
        jsx('div', { style: rowBetween, children: [
          jsx('p', { style: muted, children: `Average ${performance.average_tps ?? '—'} TPS across ${performance.tps_provider_count || 0} measured providers · trailing 24h` }),
          fastest ? jsx(Button, { onClick: () => onUseProvider(String(fastest.provider || '')), children: `Use fastest next: ${fastest.provider}` }) : null
        ] }),
        jsx('div', { style: { overflowX: 'auto' }, children: jsx('table', { style: table, children: [
          jsx('thead', { children: jsx('tr', { children: [
            jsx('th', { style: cell, children: 'Provider' }),
            jsx('th', { style: num, children: 'TPS p50' }),
            jsx('th', { style: num, children: 'TTFT ms' }),
            jsx('th', { style: num, children: 'Uptime' }),
            jsx('th', { style: num, children: 'Next request' })
          ] }) }),
          jsx('tbody', { children: perfRows.map(p => jsx('tr', { key: p.provider, children: [
            jsx('td', { style: cell, children: p.provider }),
            jsx('td', { style: num, children: p.tps_p50 ?? '—' }),
            jsx('td', { style: num, children: p.ttft_p50_ms ?? '—' }),
            jsx('td', { style: num, children: p.uptime_pct == null ? '—' : `${p.uptime_pct}%` }),
            jsx('td', { style: num, children: jsx(Button, { onClick: () => onUseProvider(String(p.provider || '')), children: 'Use next' }) })
          ] })) })
        ] }) })
      ] }),
      bookError ? jsx(ErrorState, { message: bookError }) : !book ? jsx(GlyphSpinner, {}) :
        jsx('div', { style: { overflowX: 'auto' }, children: jsx('table', { style: table, children: [
          jsx('thead', { children: jsx('tr', { children: [
            jsx('th', { style: cell, children: 'Provider' }),
            jsx('th', { style: num, children: 'Price /1M' }),
            jsx('th', { style: num, children: 'Healthy sellers' }),
            jsx('th', { style: cell, children: 'Trusted' })
          ] }) }),
          jsx('tbody', { children: (book.offers || (book.market && (book.market.offers || book.market.providers)) || []).map((o, i) => jsx('tr', { key: i, children: [
            jsx('td', { style: cell, children: String(o.provider || o.id || '—') }),
            jsx('td', { style: num, children: usdPer1m((o.price_usd_per_1m ?? o.price_per_1m ?? o.best_price_per_1m ?? o.best_input_per_1m) / 1000000) }),
            jsx('td', { style: num, children: o.healthy_sellers ?? o.healthy_seller_count ?? o.capacity ?? '—' }),
            jsx('td', { style: cell, children: o.trusted ? jsx(Badge, { children: 'trusted' }) : '—' })
          ] })) })
        ] }) })
    ] }) : null
  ] })
}

function ProvidersView({ ctx, onUseProvider }) {
  const [trustedOnly, setTrustedOnly] = useState(false)
  const [providers, error] = useSurp(ctx, '/providers', [])
  if (error) return jsx(ErrorState, { message: error })
  if (!providers) return jsx(GlyphSpinner, {})
  const rows = (providers.providers || []).filter(p => !trustedOnly || p.trusted)
  const sorted = [...rows].sort((a, b) => Number((b.market && b.market.healthy_sellers) || 0) - Number((a.market && a.market.healthy_sellers) || 0))
  return jsxs('div', { style: { display: 'grid', gap: 16 }, children: [
    jsx('div', { style: rowBetween, children: [
      jsx('p', { style: muted, children: `${rows.length} providers · trust and live market coverage. Open a model for per-model TPS.` }),
      jsx('label', { style: { display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--ui-text-secondary)' }, children: ['Trusted only', jsx(Switch, { checked: trustedOnly, onCheckedChange: setTrustedOnly })] })
    ] }),
    jsx('div', { style: { overflowX: 'auto' }, children: jsx('table', { style: table, children: [
      jsx('thead', { children: jsx('tr', { children: [
        jsx('th', { style: cell, children: 'Provider' }),
        jsx('th', { style: num, children: 'Healthy sellers' }),
        jsx('th', { style: num, children: 'Models' }),
        jsx('th', { style: cell, children: 'Trust' }),
        jsx('th', { style: num, children: 'Next request' })
      ] }) }),
      jsx('tbody', { children: sorted.map(p => {
        const id = String(p.provider || p.id || p.name || '')
        return jsx('tr', { key: id, children: [
          jsx('td', { style: cell, children: id }),
          jsx('td', { style: num, children: (p.market && p.market.healthy_sellers) ?? '—' }),
          jsx('td', { style: num, children: (p.market && p.market.models) ?? '—' }),
          jsx('td', { style: cell, children: p.trusted ? jsx(Badge, { children: 'trusted' }) : jsx('span', { style: { color: 'var(--ui-text-tertiary)' }, children: 'untrusted' }) }),
          jsx('td', { style: num, children: jsx(Button, { onClick: () => onUseProvider(id), children: 'Use next' }) })
        ] })
      }) })
    ] }) })
  ] })
}

const OBJECTIVES = ['', 'price', 'latency', 'balanced']

function RouterView({ ctx }) {
  const [prefsData, prefsError] = useSurp(ctx, '/prefs', [])
  const [prefs, setPrefs] = useState(null)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState(null)
  useEffect(() => { if (prefsData && prefsData.prefs) setPrefs(prefsData.prefs) }, [prefsData])
  const [combosData] = useSurp(ctx, '/combos', [])
  const routes = (combosData && combosData.combos ? combosData.combos.map(c => String(c.combo || c.id || '')).filter(Boolean) : ['surp/best-chat', 'surp/best-coding', 'surp/best-reasoning', 'surp/jev'])
  const combosError = combosData && combosData.ok === false ? (combosData.error || 'could not load combos') : null
  if (prefsError) return jsx(ErrorState, { message: prefsError })
  if (!prefs) return jsx(GlyphSpinner, {})
  const save = patch => {
    setPrefs(p => ({ ...p, ...patch }))
    setSaving(true)
    ctx.rest('/prefs', { method: 'POST', body: patch }).then(
      value => { setSaving(false); if (value && value.prefs) { setPrefs(value.prefs); setSavedAt(new Date().toLocaleTimeString()) } },
      () => setSaving(false)
    )
  }
  const toggleList = (key, name) => {
    const list = [...(prefs[key] || [])]
    const i = list.indexOf(name)
    if (i >= 0) list.splice(i, 1); else list.push(name)
    save({ [key]: list })
  }
  return jsxs('div', { style: { display: 'grid', gap: 16 }, children: [
    jsx('div', { style: card, children: [
      jsx('div', { style: rowBetween, children: [
        jsxs('div', { children: [
          jsx('h2', { style: { fontSize: 16, margin: 0 }, children: 'Trusted only' }),
          jsx('p', { style: muted, children: 'Route only to providers on the trusted allowlist.' })
        ] }),
        jsx(Switch, { checked: !!prefs.trusted_only, onCheckedChange: v => save({ trusted_only: !!v }) })
      ] })
    ] }),
    jsx('div', { style: card, children: [
      jsx('div', { style: rowBetween, children: [
        jsxs('div', { children: [
          jsx('h2', { style: { fontSize: 16, margin: 0 }, children: 'Secret masking' }),
          jsx('p', { style: muted, children: 'Mask secrets in prompts before they reach the seller (X-SI-Mask-Secrets).' })
        ] }),
        jsx(Switch, { checked: !!prefs.mask_secrets, onCheckedChange: v => save({ mask_secrets: !!v }) })
      ] })
    ] }),
    jsx('div', { style: card, children: [
      jsx('h2', { style: { fontSize: 16, margin: 0 }, children: 'Routing objective' }),
      jsx(SegmentedControl, { value: prefs.objective || '', onChange: v => save({ objective: v || null }), options: [
        { id: '', label: 'Router default' },
        { id: 'price', label: 'Cheapest' },
        { id: 'latency', label: 'Fastest' },
        { id: 'balanced', label: 'Balanced' }
      ] })
    ] }),
    jsx('div', { style: card, children: jsx(PresetRow, { label: 'Minimum discount vs external list price', values: [0, 10, 25, 50, 75, 90], current: prefs.min_discount, suffix: '%', onPick: value => save({ min_discount: value }) }) }),
    jsx('div', { style: card, children: [
      jsx('h2', { style: { fontSize: 16, margin: 0 }, children: 'Blocked providers' }),
      jsx('p', { style: muted, children: (prefs.block_providers || []).length ? (prefs.block_providers || []).join(', ') : 'None — every provider is eligible.' }),
      jsx(BlockAdder, { ctx, onAdd: name => toggleList('block_providers', name), current: prefs.block_providers || [] })
    ] }),
    jsx('div', { style: card, children: [
      jsx('h2', { style: { fontSize: 16, margin: 0 }, children: 'Preferred providers' }),
      jsx('p', { style: muted, children: (prefs.prefer_providers || []).length ? (prefs.prefer_providers || []).join(' → ') : 'No preference — cheapest first.' }),
      jsx(BlockAdder, { ctx, onAdd: name => toggleList('prefer_providers', name), current: prefs.prefer_providers || [] })
    ] }),
    jsx('p', { role: 'status', 'aria-live': 'polite', style: muted, children: saving ? 'Saving…' : savedAt ? `Saved ${savedAt} — applies to the next surp_chat call.` : 'Changes apply to the next surp_chat call.' })
  ] })
}

function BlockAdder({ ctx, onAdd, current }) {
  const [text, setText] = useState('')
  const submit = event => {
    event.preventDefault()
    const name = text.trim().toLowerCase()
    if (!name) return
    onAdd(name)
    setText('')
  }
  return jsxs('form', { onSubmit: submit, style: { display: 'flex', gap: 8 }, children: [
    jsx('input', { value: text, onChange: e => setText(e.target.value), placeholder: 'provider name, e.g. openrouter', 'aria-label': 'Provider name', style: { ...control, flex: 1 } }),
    jsx(Button, { type: 'submit', children: current.includes(text.trim().toLowerCase()) && text.trim() ? 'Remove' : 'Add' })
  ] })
}

function ProviderChoice({ row, mode, current, onChoose }) {
  const name = String(row.provider || '')
  const price = row.price_usd_per_1m == null ? '—' : `$${Number(row.price_usd_per_1m).toFixed(4)}/1M`
  const discount = row.discount_pct == null ? 'discount —' : `${row.discount_pct}% off`
  const tps = row.tps_p50 == null ? 'TPS —' : `${row.tps_p50} TPS`
  const reliability = `${row.ttft_p50_ms ?? '—'}ms TTFT · ${row.uptime_pct ?? '—'}% uptime`
  return jsxs('button', { type: 'button', onClick: () => onChoose(name), style: providerRow, children: [
    jsxs('span', { children: [
      jsxs('strong', { children: [name, current ? ' ✓' : ''] }),
      jsxs('span', { style: { ...muted, display: 'block' }, children: [`${row.trusted ? 'trusted' : 'untrusted'} · ${discount}`] })
    ] }),
    jsxs('span', { style: { textAlign: 'right', fontVariantNumeric: 'tabular-nums' }, children: [
      jsx('strong', { children: mode === 'tps' ? tps : price }),
      jsx('span', { style: { ...muted, display: 'block' }, children: mode === 'tps' ? reliability : tps })
    ] })
  ] })
}

function PresetRow({ label, values, current, onPick, suffix = '' }) {
  return jsxs('div', { style: { display: 'grid', gap: 8 }, children: [
    jsx('span', { style: muted, children: label }),
    jsx('div', { style: { display: 'flex', gap: 8, flexWrap: 'wrap' }, children: values.map(value => jsx('button', {
      type: 'button', onClick: () => onPick(value), style: { ...composerTrigger, color: Number(current || 0) === value ? 'var(--ui-accent)' : 'var(--ui-text-secondary)' },
      children: value === 0 ? 'Auto' : `${value}${suffix}`
    }, value)) })
  ] })
}

function ComposerMarketMenu({ ctx, kind }) {
  const model = String(useValue(host.state.model) || '')
  const [open, setOpen] = useState(false)
  const path = open && model ? `/composer/market?model=${encodeURIComponent(model)}` : null
  const [data, error, setData] = useSurp(ctx, path, [path])
  useEffect(() => { setOpen(false) }, [model])
  const ready = data && data.board && String(data.board.model).toLowerCase() === model.toLowerCase()
  const board = ready ? data.board : null
  const prefs = ready ? data.prefs : {}
  const rows = board ? (kind === 'tps' ? board.fastest : board.cheapest) : []
  const save = patch => ctx.rest('/prefs', { method: 'POST', body: patch }).then(value => {
    if (value && value.prefs) setData(current => ({ ...current, prefs: value.prefs }))
    return value
  }, err => {
    host.notify({ kind: 'error', message: `SURP preference was not saved: ${String((err && err.message) || err)}` })
    return null
  })
  const choose = name => {
    const blocked = (prefs.block_providers || []).filter(p => p !== name)
    save({ prefer_providers: [name], block_providers: blocked }).then(value => { if (value) setOpen(false) })
  }
  const auto = () => save({ prefer_providers: [] }).then(value => { if (value) setOpen(false) })
  const title = kind === 'tps' ? 'Fast TPS' : 'Cheapest 5'
  return jsxs(Popover, { open, onOpenChange: setOpen, children: [
    jsx(PopoverTrigger, { asChild: true, children: jsx('button', { type: 'button', disabled: !model, 'aria-label': kind === 'tps' ? 'Fast TPS' : 'Cheapest 5 providers', style: composerTrigger, children: title }) }),
    open ? jsxs(PopoverContent, { side: 'top', align: 'end', variant: 'menu', style: { width: 430, maxWidth: 'calc(100vw - 32px)', maxHeight: 620, overflowY: 'auto', padding: 12 }, children: [
      jsxs('div', { style: { display: 'grid', gap: 12 }, children: [
        jsxs('div', { style: rowBetween, children: [
          jsxs('div', { children: [
            jsx('h2', { style: { fontSize: 16, margin: 0 }, children: title }),
            jsx('p', { style: muted, children: model || 'No model selected' })
          ] }),
          jsx(Button, { onClick: auto, children: 'Auto provider' })
        ] }),
        board && board.best_discount_pct != null ? jsx('p', { style: muted, children: `Best live discount ${board.best_discount_pct}% · prices and discounts from the current order book` }) : null,
        kind === 'tps' && board && board.average_tps != null ? jsx('p', { style: muted, children: `Average ${board.average_tps} TPS · trailing 24h` }) : null,
        error ? jsx(ErrorState, { message: error }) : !ready ? jsx(GlyphSpinner, {}) : jsxs('div', { style: { display: 'grid', gap: 8 }, children: rows.map(row => jsx(ProviderChoice, {
          row, mode: kind, current: (prefs.prefer_providers || [])[0] === row.provider, onChoose: choose
        }, row.provider)) }),
        board && board.performance_error ? jsx('p', { style: muted, children: 'TPS data is unavailable for this model. Price and discount choices remain live.' }) : null,
        kind === 'tps' ? jsx(PresetRow, { label: 'Minimum TPS', values: [0, 25, 50, 100, 200], current: prefs.min_tps, suffix: ' TPS', onPick: value => save({ min_tps: value }) }) : jsx(PresetRow, { label: 'Minimum discount vs external list price', values: [0, 10, 25, 50, 75, 90], current: prefs.min_discount, suffix: '%', onPick: value => save({ min_discount: value }) }),
        jsx('label', { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, fontSize: 13, color: 'var(--ui-text-secondary)' }, children: ['Trusted providers only', jsx(Switch, { checked: !!prefs.trusted_only, onCheckedChange: value => save({ trusted_only: !!value }) })] }),
        jsx('p', { style: muted, children: 'Changes apply to subsequent surp_chat requests. No inference is sent from this menu.' })
      ] })
    ] }) : null
  ] })
}

function SurpComposerControls({ ctx }) {
  return jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: 8 }, children: [
    jsx(ComposerMarketMenu, { ctx, kind: 'tps' }),
    jsx(ComposerMarketMenu, { ctx, kind: 'price' })
  ] })
}

function SurpPage({ ctx }) {
  const [tab, setTab] = useState('markets')
  const [prefsData, prefsError, setPrefsData] = useSurp(ctx, '/prefs', [])
  const [combosData] = useSurp(ctx, '/combos', [])
  const routes = (combosData && combosData.combos ? combosData.combos.map(c => String(c.combo || c.id || '')).filter(Boolean) : ['surp/best-chat', 'surp/best-coding', 'surp/best-reasoning', 'surp/jev'])
  const [snapshot, setSnapshot] = useState(null)
  const [minTps, setMinTps] = useState('')
  const [routeNote, setRouteNote] = useState(null)
  useEffect(() => {
    if (prefsData && prefsData.prefs) {
      setSnapshot(prefsData.prefs.default_route || 'surp/best-chat')
      setMinTps(prefsData.prefs.min_tps == null ? '' : String(prefsData.prefs.min_tps))
    }
  }, [prefsData])
  const activeCombo = ((combosData && combosData.combos) || []).find(c => String(c.combo || c.id || '') === snapshot)
  const resolvedModel = activeCombo && (activeCombo.resolved_model || activeCombo.routes_to_now)
  const [routePerformance] = useSurp(ctx, resolvedModel ? `/performance/${encodeURIComponent(resolvedModel)}` : null, [resolvedModel])
  const updatePrefs = (patch, note) => {
    setRouteNote('Saving…')
    return ctx.rest('/prefs', { method: 'POST', body: patch }).then(
      value => {
        if (value && value.prefs) setPrefsData(value)
        setRouteNote(note)
        return value
      },
      err => { setRouteNote(`Could not save: ${String((err && err.message) || err)}`); return null }
    )
  }
  const useProvider = name => {
    if (!name) return
    const blocked = ((prefsData && prefsData.prefs && prefsData.prefs.block_providers) || []).filter(p => p !== name)
    updatePrefs(
      { prefer_providers: [name], block_providers: blocked },
      `${name} is saved as the first choice for the next surp_chat request, subject to trust and TPS filters. Other providers remain available for failover.`
    )
  }
  const saveMinTps = event => {
    event.preventDefault()
    const value = minTps.trim() === '' ? 0 : Number(minTps)
    if (!Number.isFinite(value) || value < 0 || value > 100000) {
      setRouteNote('TPS floor must be between 0 and 100000.')
      return
    }
    updatePrefs({ min_tps: value }, value > 0
      ? `Saved ${value} TPS floor. Slower and unmeasured providers will be excluded before the next paid request.`
      : 'TPS floor cleared. All otherwise eligible providers can serve the next request.')
  }
  const [draftNote, setDraftNote] = useState(null)
  const pickDefault = value => {
    setSnapshot(value)
    ctx.rest('/prefs', { method: 'POST', body: { default_route: value } })
  }
  const draftInChat = (model, maxTokens) => {
    const text = `Via the surp_chat tool, run model ${model} with max_tokens=${maxTokens} on this message: `
    host.composer.insertText(null, text, { mode: 'inline' }).then(ok => {
      haptic(ok ? 'tap' : 'error')
      setDraftNote(ok ? `Drafted in the composer with ${model}. Review, write your prompt after it, and send — the spend-approval prompt fires before anything is paid.` : 'No chat surface answered. Open a chat first, then tap this again.')
    })
  }
  return jsxs('main', { style: main, children: [
    jsxs('header', { children: [
      jsx('p', { style: { fontSize: 12, color: 'var(--ui-text-tertiary)', margin: 0 }, children: 'SURP · LIVE MARKETPLACE' }),
      jsx('h1', { style: { fontSize: 28, letterSpacing: '-1px', margin: '8px 0' }, children: 'Marketplace' }),
      jsx('p', { style: { ...muted, fontSize: 14 }, children: 'Live Surplus Intelligence prices, provider speed and trust, and your router — the same data and switches the surp_* agent tools use.' })
    ] }),
    jsx('div', { style: { display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }, children: [
      jsx(SegmentedControl, { value: tab, onChange: setTab, options: [
        { id: 'markets', label: 'Prices' },
        { id: 'providers', label: 'Providers' },
        { id: 'router', label: 'Router' }
      ] }),
      jsx('label', { style: { ...field, minWidth: 220 }, children: ['Default route', prefsData ? jsxs(Select, { value: snapshot, onValueChange: pickDefault, children: [
        jsx(SelectTrigger, { style: control, children: jsx(SelectValue, {}) }),
        jsx(SelectContent, { children: routes.map(m => jsx(SelectItem, { value: m, children: m }, m)) })
      ] }) : jsx(GlyphSpinner, {})] })
    ] }),
    jsxs('section', { style: card, children: [
      jsx('div', { style: rowBetween, children: [
        jsxs('div', { children: [
          jsx('h2', { style: { fontSize: 16, margin: 0 }, children: 'Provider speed' }),
          jsx('p', { style: muted, children: `${resolvedModel || 'Current route'} · average provider p50, trailing 24h. A routing signal, not a guarantee.` })
        ] }),
        jsx('strong', { style: { fontSize: 24, fontVariantNumeric: 'tabular-nums' }, children: routePerformance && routePerformance.average_tps != null ? `${routePerformance.average_tps} TPS` : '—' })
      ] }),
      jsxs('form', { onSubmit: saveMinTps, style: { display: 'flex', gap: 8, alignItems: 'end', flexWrap: 'wrap' }, children: [
        jsxs('label', { style: { ...field, minWidth: 220 }, children: [
          'Desired minimum TPS (0 clears)',
          jsx('input', { type: 'number', min: 0, max: 100000, step: 'any', value: minTps, onChange: e => setMinTps(e.target.value), 'aria-label': 'Desired minimum TPS', style: control })
        ] }),
        jsx(Button, { type: 'submit', children: 'Save TPS floor' })
      ] }),
      routeNote ? jsx('p', { role: 'status', 'aria-live': 'polite', style: muted, children: routeNote }) : null
    ] }),
    tab === 'markets' ? jsx(MarketsView, { ctx, onUseProvider: useProvider }) : tab === 'providers' ? jsx(ProvidersView, { ctx, onUseProvider: useProvider }) : jsx(RouterView, { ctx }),
    tab === 'markets' ? jsx('div', { style: card, children: [
      jsx('h2', { style: { fontSize: 16, margin: 0 }, children: 'Send via the agent' }),
      jsx('p', { style: muted, children: 'Paid requests are never sent from this page. The button below drafts a surp request in the chat composer — you review it, you send it, and the spend-approval prompt fires before anything is paid.' }),
      jsx('div', { style: { display: 'flex', gap: 8 }, children: jsx(Button, { onClick: () => draftInChat(snapshot, 1500), children: `Draft ${snapshot} in chat` }) }),
      draftNote ? jsx('p', { role: 'status', style: { ...muted, fontSize: 13 }, children: draftNote }) : null
    ] }) : null
  ] })
}

export default {
  id: ID,
  name: 'SURP Marketplace',
  defaultEnabled: false,
  register(ctx) {
    ctx.i18n.register({ en: { pageTitle: 'SURP Marketplace' } })
    ctx.register({ id: 'page', area: ROUTES_AREA, data: { path: '/surp' }, render: () => jsx(SurpPage, { ctx }) })
    ctx.register({ id: 'composer-actions', area: COMPOSER_AREAS.actions, render: () => jsx(SurpComposerControls, { ctx }) })
    ctx.register({ id: 'nav', area: SIDEBAR_NAV_AREA, data: { path: '/surp', label: 'SURP', codicon: 'graph' } })
    ctx.register({ id: 'open', area: PALETTE_AREA, data: { id: 'surp.open', label: 'SURP: open marketplace', keywords: ['surp', 'marketplace', 'prices', 'router'], run: () => host.navigate('/surp') } })
  }
}
