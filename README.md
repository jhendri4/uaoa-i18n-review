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

Prefer the **standalone** repo so Render’s root is the app (not the elearning monorepo):

1. Create a fine-grained GitHub PAT with **Contents: Read & write** on `jhendri4/uaoa-i18n-review` only.
2. One-click Blueprint (first time), or open the existing service:

   https://dashboard.render.com/blueprints/new?repo=https%3A%2F%2Fgithub.com%2Fjhendri4%2Fuaoa-i18n-review

3. Set env var **`GITHUB_TOKEN`** to that PAT (repo already sets `GITHUB_REPO` / `GITHUB_BRANCH` in `render.yaml`).
4. Deploy. Health check: `GET /api/health` → `{"ok":true,"storage":"github",...}`.

**Redeploy after API changes:** push to `jhendri4/uaoa-i18n-review` `main` (auto-deploy if the Render service is linked), or **Manual Deploy** in the Render dashboard.

**CLI (optional):** `brew install render` → `render login` → `render deploys create` for service `uaoa-i18n-review-api`.

Free-tier services sleep when idle; the first request after sleep can take ~30–60s.

## Point Pages at the API

In both this folder and the Pages repo, `config.js` should be:

```js
window.UAOA_I18N_REVIEW = {
  apiBase: 'https://uaoa-i18n-review-api.onrender.com',
  // ...
};
```

Bump the `?v=` query on the script tags in `index.html` when changing `config.js` / `app.js` so browsers pick up the new API URL.

## Sync catalogs

From the elearning monorepo:

```bash
python3 tools/i18n-review/scripts/sync_catalogs.py
# then copy tools/i18n-review/data → uaoa-i18n-review and push
```

Reviewed `data/<locale>.json` can be copied back into `source/i18n/`.
