#!/usr/bin/env python3
"""UAOA i18n review API + static file server.

Local (filesystem state):
  cd tools/i18n-review && python3 api/server.py

GitHub-backed (shared locks / saves for public reviewers):
  export GITHUB_TOKEN=ghp_...
  export GITHUB_REPO=jhendri4/uaoa-i18n-review
  export GITHUB_BRANCH=main
  python3 api/server.py --port 8787

The GitHub token stays on the server — the public page never sees it.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
STATE = ROOT / 'state'
LOCKS = STATE / 'locks'
APPROVALS = STATE / 'approvals'
LOCALES = {'es', 'cs', 'sl', 'sv', 'fr'}

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN') or ''
GITHUB_REPO = os.environ.get('GITHUB_REPO', '')
GITHUB_BRANCH = os.environ.get('GITHUB_BRANCH', 'main')
USE_GITHUB = bool(GITHUB_TOKEN and GITHUB_REPO)

# Render / slim images often lack a working system CA bundle; prefer certifi.
try:
    import certifi

    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    SSL_CONTEXT = ssl.create_default_context()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def cors(handler: SimpleHTTPRequestHandler) -> None:
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,OPTIONS')
    # Echo requested headers when present so browser preflights (custom headers
    # like Bypass-Tunnel-Reminder from older clients) succeed against github.io.
    req_hdrs = handler.headers.get('Access-Control-Request-Headers')
    allow = req_hdrs or 'Content-Type, Accept, Bypass-Tunnel-Reminder'
    handler.send_header('Access-Control-Allow-Headers', allow)
    handler.send_header('Access-Control-Max-Age', '86400')


def read_json_body(handler: SimpleHTTPRequestHandler) -> dict:
    length = int(handler.headers.get('Content-Length') or 0)
    raw = handler.rfile.read(length) if length else b'{}'
    try:
        data = json.loads(raw.decode('utf-8') or '{}')
    except json.JSONDecodeError as e:
        raise ValueError(f'invalid JSON: {e}') from e
    if not isinstance(data, dict):
        raise ValueError('JSON body must be an object')
    return data


def send_json(handler: SimpleHTTPRequestHandler, status: int, payload: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    cors(handler)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


# --- storage helpers ---------------------------------------------------------

def gh_api(method: str, path: str, body: dict | None = None) -> dict:
    url = f'https://api.github.com{path}'
    data = None if body is None else json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'uaoa-i18n-review',
            'Content-Type': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as res:
            raw = res.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'GitHub {method} {path} -> {e.code}: {err[:400]}') from e
    except urllib.error.URLError as e:
        raise RuntimeError(f'GitHub {method} {path} -> network/SSL error: {e}') from e


def gh_get_file(path: str) -> tuple[Any, str | None]:
    """Return (parsed_json, sha). Missing file → (None, None)."""
    api_path = f'/repos/{GITHUB_REPO}/contents/{path}?ref={GITHUB_BRANCH}'
    try:
        meta = gh_api('GET', api_path)
    except RuntimeError as e:
        if '404' in str(e):
            return None, None
        raise
    content = base64.b64decode(meta.get('content') or '').decode('utf-8')
    sha = meta.get('sha')
    if not content.strip():
        return None, sha
    return json.loads(content), sha


def gh_put_file(path: str, obj: Any, message: str, sha: str | None) -> None:
    content = base64.b64encode(
        (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    ).decode('ascii')
    body: dict[str, Any] = {
        'message': message,
        'content': content,
        'branch': GITHUB_BRANCH,
    }
    if sha:
        body['sha'] = sha
    gh_api('PUT', f'/repos/{GITHUB_REPO}/contents/{path}', body)


def fs_read(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    text = path.read_text(encoding='utf-8').strip()
    if not text or text == 'null':
        return default
    return json.loads(text)


def fs_write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load_catalog(locale: str) -> dict:
    if locale != 'en' and locale not in LOCALES:
        raise ValueError(f'unsupported locale: {locale}')
    rel = f'data/{locale}.json'
    if USE_GITHUB:
        data, _ = gh_get_file(rel)
        if data is None:
            # fall back to bundled copy shipped with the server
            return fs_read(DATA / f'{locale}.json', {})
        return data
    return fs_read(DATA / f'{locale}.json', {})


def save_catalog(locale: str, catalog: dict, message: str) -> None:
    if locale not in LOCALES:
        raise ValueError(f'unsupported locale: {locale}')
    rel = f'data/{locale}.json'
    if USE_GITHUB:
        _, sha = gh_get_file(rel)
        gh_put_file(rel, catalog, message, sha)
    else:
        fs_write(DATA / f'{locale}.json', catalog)


def load_approvals(locale: str) -> dict:
    if locale not in LOCALES:
        raise ValueError(f'unsupported locale: {locale}')
    rel = f'state/approvals/{locale}.json'
    if USE_GITHUB:
        data, _ = gh_get_file(rel)
        return data if isinstance(data, dict) else {}
    return fs_read(APPROVALS / f'{locale}.json', {})


def save_approvals(locale: str, approvals: dict, message: str) -> None:
    rel = f'state/approvals/{locale}.json'
    if USE_GITHUB:
        _, sha = gh_get_file(rel)
        gh_put_file(rel, approvals, message, sha)
    else:
        fs_write(APPROVALS / f'{locale}.json', approvals)


def load_lock(locale: str) -> dict | None:
    if locale not in LOCALES:
        raise ValueError(f'unsupported locale: {locale}')
    rel = f'state/locks/{locale}.json'
    if USE_GITHUB:
        data, _ = gh_get_file(rel)
        lock = data if isinstance(data, dict) else None
    else:
        lock = fs_read(LOCKS / f'{locale}.json', None)
        if lock is None:
            return None
    if not lock:
        return None
    until = parse_iso(lock.get('until'))
    if until and until <= utcnow():
        return None
    return lock


def save_lock(locale: str, lock: dict | None, message: str) -> None:
    rel = f'state/locks/{locale}.json'
    payload: Any = lock
    if USE_GITHUB:
        _, sha = gh_get_file(rel)
        gh_put_file(rel, payload, message, sha)
    else:
        fs_write(LOCKS / f'{locale}.json', payload)


def set_by_path(root: dict, key: str, text: str) -> None:
    parts = key.split('.')
    cur: dict = root
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict) or (
            isinstance(nxt, dict) and 'text' in nxt and set(nxt.keys()) <= {'text', 'note'}
        ):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    leaf = parts[-1]
    existing = cur.get(leaf)
    if isinstance(existing, dict) and 'text' in existing:
        cur[leaf] = {**existing, 'text': text}
    else:
        cur[leaf] = {'text': text}


def require_holder(lock: dict | None, session_id: str) -> None:
    if not lock or lock.get('sessionId') != session_id:
        raise PermissionError('You do not hold the checkout for this locale')


# --- HTTP handler ------------------------------------------------------------

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write('%s - %s\n' % (self.address_string(), fmt % args))

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        cors(self)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path.startswith('/api/'):
                self.handle_api_get(path)
            else:
                super().do_GET()
        except Exception as e:  # noqa: BLE001
            send_json(self, 500, {'error': str(e)})

    def do_POST(self) -> None:  # noqa: N802
        self.handle_mutating('POST')

    def do_PUT(self) -> None:  # noqa: N802
        self.handle_mutating('PUT')

    def handle_mutating(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if not path.startswith('/api/'):
                send_json(self, 404, {'error': 'not found'})
                return
            body = read_json_body(self)
            self.handle_api_write(method, path, body)
        except PermissionError as e:
            send_json(self, 403, {'error': str(e)})
        except ValueError as e:
            send_json(self, 400, {'error': str(e)})
        except Exception as e:  # noqa: BLE001
            send_json(self, 500, {'error': str(e)})

    def handle_api_get(self, path: str) -> None:
        m = re.fullmatch(r'/api/catalog/([a-z]{2})', path)
        if m:
            locale = m.group(1)
            cat = load_catalog(locale)
            send_json(self, 200, {'locale': locale, 'catalog': cat})
            return
        m = re.fullmatch(r'/api/approvals/([a-z]{2})', path)
        if m:
            locale = m.group(1)
            send_json(self, 200, {'locale': locale, 'approvals': load_approvals(locale)})
            return
        m = re.fullmatch(r'/api/lock/([a-z]{2})', path)
        if m:
            locale = m.group(1)
            send_json(self, 200, {'locale': locale, 'lock': load_lock(locale)})
            return
        if path == '/api/health':
            send_json(self, 200, {
                'ok': True,
                'storage': 'github' if USE_GITHUB else 'filesystem',
                'repo': GITHUB_REPO or None,
            })
            return
        send_json(self, 404, {'error': 'not found'})

    def handle_api_write(self, method: str, path: str, body: dict) -> None:
        if path == '/api/lock/claim' and method == 'POST':
            locale = (body.get('locale') or '').strip().lower()
            name = (body.get('name') or '').strip()
            session_id = (body.get('sessionId') or '').strip()
            minutes = int(body.get('minutes') or 15)
            if locale not in LOCALES:
                raise ValueError('unsupported locale')
            if len(name) < 2 or not session_id:
                raise ValueError('name and sessionId required')
            current = load_lock(locale)
            acquired = False
            if current is None or current.get('sessionId') == session_id:
                lock = {
                    'holder': name,
                    'sessionId': session_id,
                    'until': iso(utcnow() + timedelta(minutes=max(5, min(minutes, 180)))),
                    'claimedAt': iso(utcnow()),
                }
                save_lock(locale, lock, f'i18n-review: {name} claimed {locale}')
                current = lock
                acquired = True
            send_json(self, 200, {
                'acquired': acquired,
                'lock': current,
                'approvals': load_approvals(locale),
            })
            return

        if path == '/api/lock/heartbeat' and method == 'POST':
            locale = (body.get('locale') or '').strip().lower()
            name = (body.get('name') or '').strip()
            session_id = (body.get('sessionId') or '').strip()
            minutes = int(body.get('minutes') or 15)
            current = load_lock(locale)
            if current and current.get('sessionId') == session_id:
                current = {
                    **current,
                    'holder': name or current.get('holder'),
                    'until': iso(utcnow() + timedelta(minutes=max(5, min(minutes, 180)))),
                }
                save_lock(locale, current, f'i18n-review: heartbeat {locale}')
                send_json(self, 200, {'acquired': True, 'lock': current})
            else:
                send_json(self, 200, {'acquired': False, 'lock': current})
            return

        if path == '/api/lock/release' and method == 'POST':
            locale = (body.get('locale') or '').strip().lower()
            session_id = (body.get('sessionId') or '').strip()
            current = load_lock(locale)
            if current and current.get('sessionId') == session_id:
                save_lock(locale, None, f'i18n-review: released {locale}')
            send_json(self, 200, {'ok': True})
            return

        if path == '/api/approve' and method == 'POST':
            locale = (body.get('locale') or '').strip().lower()
            key = (body.get('key') or '').strip()
            name = (body.get('name') or '').strip()
            session_id = (body.get('sessionId') or '').strip()
            require_holder(load_lock(locale), session_id)
            if not key:
                raise ValueError('key required')
            approvals = load_approvals(locale)
            entry = {'approved': True, 'by': name, 'at': iso(utcnow())}
            approvals[key] = entry
            save_approvals(locale, approvals, f'i18n-review: approve {locale} {key}')
            send_json(self, 200, {'approvals': approvals, 'entry': entry})
            return

        if path == '/api/unapprove' and method == 'POST':
            locale = (body.get('locale') or '').strip().lower()
            key = (body.get('key') or '').strip()
            session_id = (body.get('sessionId') or '').strip()
            require_holder(load_lock(locale), session_id)
            approvals = load_approvals(locale)
            approvals.pop(key, None)
            save_approvals(locale, approvals, f'i18n-review: unlock {locale} {key}')
            send_json(self, 200, {'approvals': approvals})
            return

        if path == '/api/translation' and method == 'PUT':
            locale = (body.get('locale') or '').strip().lower()
            key = (body.get('key') or '').strip()
            text = body.get('text')
            name = (body.get('name') or '').strip()
            session_id = (body.get('sessionId') or '').strip()
            require_holder(load_lock(locale), session_id)
            if not key or text is None:
                raise ValueError('key and text required')
            catalog = load_catalog(locale)
            set_by_path(catalog, key, str(text))
            save_catalog(locale, catalog, f'i18n-review: {name} updated {locale} {key}')
            send_json(self, 200, {'ok': True, 'catalog': catalog})
            return

        send_json(self, 404, {'error': 'not found'})


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8787)
    args = p.parse_args()

    LOCKS.mkdir(parents=True, exist_ok=True)
    APPROVALS.mkdir(parents=True, exist_ok=True)

    mode = f'GitHub:{GITHUB_REPO}@{GITHUB_BRANCH}' if USE_GITHUB else f'filesystem:{ROOT}'
    print(f'UAOA i18n review → http://{args.host}:{args.port}/')
    print(f'storage: {mode}')
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nbye')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
