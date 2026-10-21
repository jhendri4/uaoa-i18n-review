// Live trial API via localhost.run (ephemeral). Hard-refresh if Start reviewing 404s.
window.UAOA_I18N_REVIEW = Object.assign({
  apiBase: 'https://7afd935b073e6b.lhr.life',
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
