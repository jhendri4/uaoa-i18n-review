// Live trial API via localhost.run. Hard-refresh if Start reviewing fails.
window.UAOA_I18N_REVIEW = Object.assign({
  apiBase: 'https://37ef475326d39a.lhr.life',
  locales: [
    { code: 'es', label: 'Spanish' },
    { code: 'cs', label: 'Czech' },
    { code: 'sl', label: 'Slovenian' },
    { code: 'sv', label: 'Swedish' },
    { code: 'fr', label: 'French' },
  ],
  leaseMinutes: 30,
  pageSizeHint: 50,
}, window.UAOA_I18N_REVIEW || {});
