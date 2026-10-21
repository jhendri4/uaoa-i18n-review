// Durable API on Render (GitHub-backed locks/approvals). No local tunnels.
window.UAOA_I18N_REVIEW = Object.assign({
  apiBase: 'https://uaoa-i18n-review-api.onrender.com',
  locales: [
    { code: 'es', label: 'Spanish' },
    { code: 'cs', label: 'Czech' },
    { code: 'sl', label: 'Slovenian' },
    { code: 'sv', label: 'Swedish' },
    { code: 'fr', label: 'French' },
  ],
  leaseMinutes: 15,
  pageSizeHint: 50,
}, window.UAOA_I18N_REVIEW || {});
