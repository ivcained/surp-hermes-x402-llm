// Full SDK shim: only the surface the SURP page actually touches.
// Atoms are plain getters; every component below mirrors the host app's API
// used by the page (verified against live plugin sources in this checkout).
import React from './react.js';
import { jsx, jsxs } from './jsx.js';

export const PANES_AREA = 'panes';
export const ROUTES_AREA = 'routes';
export const SIDEBAR_NAV_AREA = 'sidebar-nav';
export const PALETTE_AREA = 'palette';
export const cn = (...a) => a.filter(Boolean).join(' ');
export const haptic = () => {};

// ---- host + atoms (inlined so the plugin's single '@hermes/plugin-sdk'
// import resolves everything it needs) ----
const __atom = v => ({ get: () => v });
export const host = {
  state: {
    focusedSessionId: __atom(null),
    focusedStoredSessionId: __atom(null),
    focusedSessionProfile: __atom('default'),
    profile: __atom('default'),
    gateway: __atom('online'),
    model: __atom('deepseek-v4.1-flash'),
  },
  navigate: p => console.log('[harness] navigate', p),
  notify: n => console.log('[harness] notify', n),
  composer: {
    insertText: async (_s, t) => { window.__harnessLastDraft = t; console.log('[harness] draft:', String(t).slice(0, 80)); return true; },
    setDraft: async () => true,
    getDraft: async () => null,
    submit: () => false,
    focus: () => {},
  },
  onEvent: () => () => {},
};

export function useValue(a) { return a.get(); }
export function Tip({ label, children }) {
  return jsx('span', { title: label, children });
}
export function SearchField({ value, onChange, placeholder }) {
  return jsx('input', { value, placeholder, 'aria-label': 'Search', onInput: e => onChange(e.target.value),
    style: { padding: '8px 12px', borderRadius: 10, border: '1px solid var(--ui-stroke-secondary)', background: 'var(--ui-bg-base)', color: 'var(--ui-text-primary)', font: 'inherit', fontSize: 13 } });
}
export function Button({ children, ...rest }) {
  return jsx('button', { type: 'button', ...rest,
    style: { padding: '10px 14px', borderRadius: 10, border: '1px solid var(--ui-stroke-secondary)', background: 'var(--ui-bg-overlay)', color: 'var(--ui-text-primary)', cursor: 'pointer', font: 'inherit', ...(rest.style || {}) } });
}
export function Switch({ checked, onCheckedChange }) {
  return jsx('button', { role: 'switch', 'aria-checked': !!checked, type: 'button',
    onClick: () => onCheckedChange && onCheckedChange(!checked),
    style: { width: 36, height: 20, borderRadius: 999, border: '1px solid var(--ui-stroke-secondary)', background: checked ? 'var(--ui-accent)' : 'transparent', cursor: 'pointer', padding: 0 } },
    jsx('span', { style: { display: 'block', width: 14, height: 14, borderRadius: 999, background: checked ? 'var(--ui-bg-base)' : 'var(--ui-text-tertiary)', margin: 2, marginLeft: checked ? 18 : 2, transition: 'margin .1s' } }));
}
export function SegmentedControl({ value, onChange, options }) {
  return jsx('div', { role: 'tablist',
    style: { display: 'inline-flex', gap: 4, padding: 4, borderRadius: 10, border: '1px solid var(--ui-stroke-secondary)' } },
    options.map(o => jsx('button', { key: o.id, role: 'tab', 'aria-selected': value === o.id, onClick: () => onChange(o.id),
      style: { padding: '6px 12px', borderRadius: 7, border: 0, cursor: 'pointer', font: 'inherit', fontSize: 13, background: value === o.id ? 'var(--ui-bg-overlay)' : 'transparent', color: value === o.id ? 'var(--ui-text-primary)' : 'var(--ui-text-secondary)' } }, o.label)));
}
export function Select({ value, onValueChange, children }) {
  const [open, setOpen] = React.useState(false);
  return jsx('div', { style: { position: 'relative' }, children: [
    jsx('button', { type: 'button', onClick: () => setOpen(o => !o), style: { width: '100%', textAlign: 'left' }, children: value || 'Select…' }),
    open ? jsx('div', { style: { position: 'absolute', zIndex: 5, top: '100%', left: 0, right: 0, background: 'var(--ui-bg-overlay)', border: '1px solid var(--ui-stroke-secondary)', borderRadius: 10, marginTop: 4, maxHeight: 240, overflow: 'auto' } },
      children && children.props && children.props.children && children.props.children[1] && children.props.children[1].props.children
        ? children.props.children[1].props.children.map(item => jsx('button', { key: item.props.value, type: 'button',
            onClick: () => { onValueChange(item.props.value); setOpen(false); },
            style: { display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px', background: 'none', border: 0, color: 'var(--ui-text-primary)', cursor: 'pointer' } }, item.props.children))
        : null) : null] });
}
export function SelectTrigger({ children, style }) { return children; }
export function SelectValue() { return null; }
export function SelectContent({ children }) { return children; }
export function SelectItem() { return null; }
export function Badge({ children }) {
  return jsx('span', { style: { fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 999, border: '1px solid var(--ui-stroke-secondary)', color: 'var(--ui-text-secondary)', textTransform: 'uppercase' } }, children);
}
export function GlyphSpinner() {
  return jsx('div', { role: 'status', style: { padding: 24, color: 'var(--ui-text-tertiary)' } }, 'Loading…');
}
export function EmptyState({ title }) {
  return jsx('div', { style: { padding: 24, color: 'var(--ui-text-tertiary)' } }, title || 'Nothing here');
}
export function ErrorState({ message }) {
  return jsx('div', { role: 'alert', style: { padding: 16, borderRadius: 12, border: '1px solid #a33', color: 'var(--ui-text-primary)' } }, 'Error: ' + message);
}
export function usePluginI18n() { return (k, ...a) => (typeof k === 'string' ? k : '') + (a.length ? ' ' + a.join(' ') : ''); }
