#!/usr/bin/env python3
"""Copy catalogs from sibling uaoa-elearning repo when available."""
from __future__ import annotations
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
DST = HERE / 'data'
LOCALES = ('en', 'es', 'cs', 'sl', 'sv', 'fr')
CANDIDATES = [
    HERE.parent / 'uaoa-elearning' / 'source' / 'i18n',
    Path('/Users/jhendri4/Documents/GitHub/uaoa-elearning/source/i18n'),
]

def main() -> None:
    src_dir = next((p for p in CANDIDATES if p.is_dir()), None)
    if not src_dir:
        raise SystemExit('Could not find uaoa-elearning/source/i18n')
    DST.mkdir(parents=True, exist_ok=True)
    for loc in LOCALES:
        src = src_dir / f'{loc}.json'
        if src.is_file():
            shutil.copy2(src, DST / f'{loc}.json')
            print('copied', src.name)
    print('done →', DST)

if __name__ == '__main__':
    main()
