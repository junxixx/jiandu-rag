"""首页推荐区简牍卡片字段（热点 / 为你 / 同好 / 编联 共用）。"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

_DJ_SPLIT_RE = re.compile(r"^DJ-(train|val|test)-", re.IGNORECASE)


def dj_subset_bucket(code: str | None) -> str:
    m = _DJ_SPLIT_RE.match((code or "").strip())
    if m:
        return m.group(1).lower()
    return "other"


def corpus_hint_from_code(code: str | None) -> str | None:
    b = dj_subset_bucket(code)
    if b != "other":
        return f"影像语料 · {b}"
    if (code or "").strip().upper().startswith("DJ-"):
        return "影像语料"
    return None


def transcription_snippet(txt: str | None, max_len: int = 80) -> str:
    if not txt or not str(txt).strip():
        return ""
    s = " ".join(str(txt).split())
    if len(s) <= max_len:
        return s
    return s[:max_len] + "…"


def slip_home_card_dict(
    row: Any,
    *,
    read_count: Optional[int] = None,
    catalog_fill: bool = False,
    snippet_max: int = 80,
) -> Dict[str, Any]:
    return {
        "id": int(row.id),
        "code": row.code,
        "title": row.title,
        "site_name": row.site_name,
        "image_url": row.image_url,
        "snippet": transcription_snippet(getattr(row, "transcription", None), snippet_max),
        "read_count": read_count,
        "catalog_fill": bool(catalog_fill),
        "corpus_hint": corpus_hint_from_code(getattr(row, "code", None)),
    }
