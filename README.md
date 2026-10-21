# UAOA Translation Review

Public review UI for approving / editing course translations.

- English (read-only) on the left, translation on the right  
- **Approve** locks a string; **Edit** opens a textarea  
- Grouped by module → widget  
- Locale via dropdown or `?locale=es` (Spanish, Czech, Slovenian, Swedish, French)  
- Locale checkout lease (one active editor per language) after entering your name  

## Quick start (local)

```bash
cd tools/i18n-review
python3 scripts/sync_catalogs.py   # refresh from source/i18n
python3 api/server.py              # http://127.0.0.1:8787/
```

Filesystem mode stores locks / approvals / edits under `state/` and `data/`.

## Shared / public mode (GitHub-backed API)

The browser is public and unauthenticated (name only). Writes go through this API so the GitHub token never ships to clients.

```bash
export GITHUB_TOKEN=github_pat_...   # contents:write on uaoa-i18n-review
export GITHUB_REPO=jhendri4/uaoa-i18n-review
export GITHUB_BRANCH=main
python3 api/server.py --host 0.0.0.0 --port 8787
```

Point the static site at the API by editing `config.js`:

```js
window.UAOA_I18N_REVIEW = { apiBase: 'https://YOUR-API-HOST' };
```

Or host UI + API together (same origin) by serving with `api/server.py`.

### Free host option (Render)

`render.yaml` defines a web service that runs `api/server.py`. Set env vars `GITHUB_TOKEN`, `GITHUB_REPO`, `GITHUB_BRANCH` in the Render dashboard.

## Sync reviewed strings back into elearning

After reviewers finish, copy `data/<locale>.json` into `source/i18n/` (or open a PR from the review repo).

## Lease behaviour

- Claiming a locale stores `state/locks/<locale>.json` with holder + expiry (default 30 minutes).  
- Heartbeat every 2 minutes while the tab is open.  
- Others can still browse that locale read-only.  
- Stale leases expire automatically.
