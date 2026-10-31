// host shim: state atoms, navigation, composer; events are no-ops.
const atom = v => ({ get: () => v });
export const host = {
  state: {
    focusedSessionId: atom(null),
    focusedStoredSessionId: atom(null),
    focusedSessionProfile: atom('default'),
    profile: atom('default'),
    gateway: atom('online'),
    model: atom('deepseek-v4.1-flash'),
  },
  navigate: p => console.log('[harness] navigate', p),
  notify: n => console.log('[harness] notify', n),
  composer: {
    insertText: async (_s, t) => { window.__harnessLastDraft = t; console.log('[harness] draft:', t); return true; },
    setDraft: async () => true,
    getDraft: async () => null,
    submit: () => false,
    focus: () => {},
  },
  onEvent: () => () => {},
};
export function useValue(a) { return a.get(); }
