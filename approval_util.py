"""Sticky approvals keyed to English source fingerprints.

An approval stays valid only while the English source string for that key
matches the fingerprint stored at approve time. Locale catalog edits alone
do not invalidate approvals.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


def iso_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace('+00:00', 'Z')
    )


def leaf_text(node: Any) -> str:
    if node is None:
        return ''
    if isinstance(node, str):
        return node
    if isinstance(node, dict) and isinstance(node.get('text'), str):
        return node['text']
    return ''


def flatten_catalog(obj: Any, prefix: str = '') -> dict[str, str]:
    """Return dotted-key → leaf text for a locale catalog (skips _meta keys)."""
    out: dict[str, str] = {}
    if not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        if str(k).startswith('_'):
            continue
        path = f'{prefix}.{k}' if prefix else str(k)
        if isinstance(v, dict) and 'text' in v:
            out[path] = leaf_text(v)
        elif isinstance(v, dict):
            out.update(flatten_catalog(v, path))
        elif isinstance(v, str):
            out[path] = v
    return out


def en_fingerprint(text: str) -> str:
    """SHA-256 hex of UTF-8 English source text."""
    return hashlib.sha256((text or '').encode('utf-8')).hexdigest()


def normalize_raw_entry(raw: Any) -> dict[str, Any] | None:
    """Coerce legacy shapes (true / {by} / full object) into a dict, or None."""
    if raw is True:
        return {'approved': True}
    if raw is False or raw is None:
        return None
    if isinstance(raw, dict):
        entry = dict(raw)
        if 'approved' not in entry and not entry.get('stale'):
            # Legacy {by} / {reviewer} without approved flag → treat as approved
            entry['approved'] = True
        if 'by' not in entry and entry.get('reviewer'):
            entry['by'] = entry.pop('reviewer')
        return entry
    return None


def make_approval(by: str, en_text: str, *, at: str | None = None) -> dict[str, Any]:
    return {
        'approved': True,
        'by': by or '',
        'at': at or iso_now(),
        'enFp': en_fingerprint(en_text),
    }


def reconcile_approvals(
    approvals: dict[str, Any],
    en_by_key: dict[str, str],
    *,
    mark_stale: bool = True,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Validate / migrate approvals against current English source strings.

    Rules:
    - Key removed from EN → drop approval
    - Missing enFp (legacy) → backfill from current EN; keep approved (migration)
    - enFp matches current EN → keep
    - enFp mismatches → unapproved; optionally keep a stale marker for UI
    - Keys with no approval entry are left alone (new keys stay unapproved)

    Returns (reconciled_map, stats).
    """
    stats = {
        'kept': 0,
        'migrated': 0,
        'stale': 0,
        'dropped': 0,
    }
    out: dict[str, Any] = {}

    for key, raw in (approvals or {}).items():
        entry = normalize_raw_entry(raw)
        if entry is None:
            stats['dropped'] += 1
            continue

        if key not in en_by_key:
            stats['dropped'] += 1
            continue

        current_fp = en_fingerprint(en_by_key[key])
        stored_fp = entry.get('enFp')

        if not stored_fp:
            # Migration: bind to current EN so re-sync of identical source keeps approval
            entry = {
                **entry,
                'approved': True,
                'stale': False,
                'enFp': current_fp,
            }
            entry.pop('staleReason', None)
            entry.pop('staleAt', None)
            out[key] = entry
            stats['migrated'] += 1
            continue

        if stored_fp == current_fp:
            if entry.get('stale') and not entry.get('approved'):
                # Still marked stale but EN matches again (source reverted) → restore
                entry = {
                    **entry,
                    'approved': True,
                    'stale': False,
                }
                entry.pop('staleReason', None)
                entry.pop('staleAt', None)
            else:
                entry = {**entry, 'approved': True, 'stale': False}
                entry.pop('staleReason', None)
                entry.pop('staleAt', None)
            out[key] = entry
            stats['kept'] += 1
            continue

        # EN source changed since approve
        if mark_stale:
            out[key] = {
                **entry,
                'approved': False,
                'stale': True,
                'staleReason': 'en_source_changed',
                'staleAt': iso_now(),
                # Keep old enFp so we know what was approved; do not update to new
            }
            stats['stale'] += 1
        else:
            stats['dropped'] += 1

    return out, stats


def is_effectively_approved(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return entry is True
    return bool(entry.get('approved')) and not entry.get('stale')
