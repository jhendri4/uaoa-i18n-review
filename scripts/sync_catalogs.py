#!/usr/bin/env python3
"""Copy latest locale catalogs from source/i18n into tools/i18n-review/data."""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # uaoa-elearning
SRC = ROOT / 'source' / 'i18n'
DST = Path(__file__).resolve().parents[1] / 'data'
LOCALES = ('en', 'es', 'cs', 'sl', 'sv', 'fr')


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


if __name__ == '__main__':
    main()
