// Override at deploy time if the API is hosted elsewhere.
// Local default: same origin (python api/server.py serves UI + API).
window.UAOA_I18N_REVIEW = Object.assign({
  apiBase: '', // e.g. 'https://uaoa-i18n-api.onrender.com'
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
