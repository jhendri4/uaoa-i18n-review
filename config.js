// Live API via Cloudflare quick tunnel → local review server.
window.UAOA_I18N_REVIEW = Object.assign({
  apiBase: 'https://remedies-satisfied-scholar-bali.trycloudflare.com',
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
