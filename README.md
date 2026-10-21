# UAOA Translation Review

Public review UI for approving / editing course translations.

- English (read-only) left · translation right  
- **Approve** locks a string · **Edit** opens a textarea · **Unlock** to revise  
- Grouped by module → widget; filter box for search  
- Locale dropdown or shareable `?locale=es`  
- Name gate on load (no account)  
- **Locale checkout lease** — one active editor per language (others read-only)

## Live UI

https://jhendri4.github.io/uaoa-i18n-review/

The Pages site is static. Shared locks/saves need the API below (token stays on the server).

## Local (UI + API together)

```bash
cd tools/i18n-review          # or the uaoa-i18n-review clone
python3 scripts/sync_catalogs.py
python3 api/server.py        # http://127.0.0.1:8787/
```

Open that URL (not the raw `index.html` file). Filesystem mode writes under `data/` + `state/`.

## Public shared mode

1. Create a fine-grained PAT with **Contents: Read & write** on `jhendri4/uaoa-i18n-review` only.
2. Host `api/server.py` (Render free tier works — see `render.yaml`):

```bash
export GITHUB_TOKEN=github_pat_...
export GITHUB_REPO=jhendri4/uaoa-i18n-review
export GITHUB_BRANCH=main
python3 api/server.py --host 0.0.0.0 --port 8787
```

3. Point the Pages site at the API by committing `config.js`:

```js
window.UAOA_I18N_REVIEW = {
  apiBase: 'https://YOUR-RENDER-SERVICE.onrender.com',
};
```

Until `apiBase` is set, use the local all-in-one server for real review sessions.

## Sync catalogs

From the elearning monorepo:

```bash
python3 tools/i18n-review/scripts/sync_catalogs.py
# then copy tools/i18n-review/data → uaoa-i18n-review and push
```

Reviewed `data/<locale>.json` can be copied back into `source/i18n/`.
