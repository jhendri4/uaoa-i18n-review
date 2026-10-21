#!/usr/bin/env python3
"""Copy latest locale catalogs from source/i18n into tools/i18n-review/data.

Also reconciles sticky approvals against English source fingerprints so that:
  - unchanged EN keys keep their approvals (legacy entries get enFp backfilled)
  - EN text that changed is marked stale / unapproved
  - removed EN keys drop their approval entries
Locale translation edits alone do not clear EN-stable approvals.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # uaoa-elearning
REVIEW = Path(__file__).resolve().parents[1]
SRC = ROOT / 'source' / 'i18n'
DST = REVIEW / 'data'
APPROVALS_DIR = REVIEW / 'state' / 'approvals'
LOCALES = ('en', 'es', 'cs', 'sl', 'sv', 'fr')
REVIEW_LOCALES = ('es', 'cs', 'sl', 'sv', 'fr')

sys.path.insert(0, str(REVIEW))
from approval_util import flatten_catalog, reconcile_approvals  # noqa: E402


def load_json(path: Path, default):
    if not path.is_file():
        return default
    text = path.read_text(encoding='utf-8').strip()
    if not text or text == 'null':
        return default
    return json.loads(text)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    for loc in LOCALES:
        src = SRC / f'{loc}.json'
        if not src.is_file():
            print('skip missing', src)
            continue
        shutil.copy2(src, DST / f'{loc}.json')
        print('copied', src.name)
    print('done →', DST)

    en_path = DST / 'en.json'
    if not en_path.is_file():
        print('no en.json — skip approval reconcile')
        return

    en_by_key = flatten_catalog(load_json(en_path, {}))
    print(f'EN strings: {len(en_by_key)}')

    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
    for loc in REVIEW_LOCALES:
        path = APPROVALS_DIR / f'{loc}.json'
        raw = load_json(path, {})
        if not isinstance(raw, dict):
            raw = {}
        reconciled, stats = reconcile_approvals(raw, en_by_key, mark_stale=True)
        if reconciled != raw:
            write_json(path, reconciled)
            print(
                f'approvals {loc}: kept={stats["kept"]} migrated={stats["migrated"]} '
                f'stale={stats["stale"]} dropped={stats["dropped"]} → wrote {path.name}'
            )
        else:
            print(
                f'approvals {loc}: kept={stats["kept"]} migrated={stats["migrated"]} '
                f'stale={stats["stale"]} dropped={stats["dropped"]} (unchanged)'
            )


if __name__ == '__main__':
    main()
