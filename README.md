# UAOA Translation Review

Public review UI for approving / editing course translations.

- English (read-only) left · translation right  
- **Approve** locks a string · **Edit** opens a textarea · **Unlock** to revise  
- Grouped by module → widget; filter box for search  
- Locale dropdown or shareable `?locale=es`  
- Name gate on load (no account)  
- **Locale checkout lease** — one active editor per language (others read-only)

## Live

| | URL |
|---|---|
| **UI (GitHub Pages)** | https://jhendri4.github.io/uaoa-i18n-review/ |
| **API (Render)** | https://uaoa-i18n-review-api.onrender.com |

The Pages site is static (`config.js` → `apiBase`). Shared locks/saves go through the Render API; the GitHub token stays on the server.

## Local (UI + API together)

```bash
cd tools/i18n-review          # or the uaoa-i18n-review clone
python3 scripts/sync_catalogs.py
python3 api/server.py        # http://127.0.0.1:8787/
```

Open that URL (not the raw `index.html` file). Filesystem mode writes under `data/` + `state/`.

## Deploy / redeploy the API (Render)

Live service: **`uaoa-i18n-review-api`** → https://uaoa-i18n-review-api.onrender.com  
Dashboard: https://dashboard.render.com/web/srv-dbcfoomktt5c73faov7g

**Redeploy after API changes:** push to `main` (auto-deploy is on), or:

```bash
brew install render   # once
render login          # once
render workspace set tea-dbcfnp3l550s73908nvg
render deploys create srv-dbcfoomktt5c73faov7g --confirm
```

**Rotate the GitHub token (recommended):** create a fine-grained PAT with **Contents: Read & write** on `jhendri4/uaoa-i18n-review` only, then in the Render dashboard set env **`GITHUB_TOKEN`**. Prefer a PAT over a short-lived `gh` OAuth token.

Health check: `GET /api/health` → `{"ok":true,"storage":"github",...}`.

Free-tier services sleep when idle; the first request after sleep can take ~30–60s.

## Point Pages at the API

`config.js` should be:

```js
window.UAOA_I18N_REVIEW = {
  apiBase: 'https://uaoa-i18n-review-api.onrender.com',
  // ...
};
```

Bump the `?v=` query on the script tags in `index.html` when changing `config.js` / `app.js`.

## Sync catalogs

From the elearning monorepo:

```bash
python3 tools/i18n-review/scripts/sync_catalogs.py
# then copy tools/i18n-review/data → uaoa-i18n-review and push
```

Reviewed `data/<locale>.json` can be copied back into `source/i18n/`.
