"""
bamboo_slips.tags 字段约定（与 Neo4j 同步一致）

- 人物：「人:」「人：」「人物:」「人物：」→ Person / MENTIONS_PERSON
- 史事：「事件:」「事件：」→ Event / RECORDS（简牍记述该事件）；同简牍人物与事件建 INVOLVES
- 其余为主题标签 → Tag / HAS_TAG
"""

from __future__ import annotations

import re
from typing import List, Tuple

_PERSON_PREFIXES = ("人物:", "人物：", "人:", "人：")
_EVENT_PREFIXES = ("事件:", "事件：")
_SPLIT_RE = re.compile(r"[,，;；\s]+")


def parse_slip_tags(tags: str | None) -> Tuple[List[str], List[str], List[str]]:
    """拆分为 (主题标签, 人物姓名列表, 事件名称列表)。"""
    if not tags or not str(tags).strip():
        return [], [], []
    parts = _SPLIT_RE.split(str(tags).strip())
    topics: List[str] = []
    persons: List[str] = []
    events: List[str] = []
    for raw in parts:
        p = raw.strip()
        if not p:
            continue
        for prefix in _PERSON_PREFIXES:
            if p.startswith(prefix):
                name = p[len(prefix) :].strip()
                if name:
                    persons.append(name[:64])
                break
        else:
            for prefix in _EVENT_PREFIXES:
                if p.startswith(prefix):
                    en = p[len(prefix) :].strip()
                    if en:
                        events.append(en[:128])
                    break
            else:
                topics.append(p[:128])
    return topics, persons, events


def format_slip_tags(
    topics: List[str], persons: List[str], events: List[str] | None = None
) -> str:
    """主题 → 事件 → 人物；人物「人:」、事件「事件:」前缀。"""
    seen: set[str] = set()
    chunks: List[str] = []
    for t in topics:
        t = (t or "").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        chunks.append(t[:128])
    for en in events or []:
        en = (en or "").strip()
        if not en:
            continue
        token = f"事件:{en[:128]}"
        if token in seen:
            continue
        seen.add(token)
        chunks.append(token)
    for name in persons:
        name = (name or "").strip()
        if not name:
            continue
        token = f"人:{name[:64]}"
        if token in seen:
            continue
        seen.add(token)
        chunks.append(token)
    return ",".join(chunks)


def normalize_slip_tags(tags: str | None, max_len: int = 500) -> str:
    t, p, e = parse_slip_tags(tags)
    s = format_slip_tags(t, p, e)
    if len(s) <= max_len:
        return s
    return s[:max_len].rstrip(",")


def append_topic(existing: str | None, topic: str) -> str:
    t, p, e = parse_slip_tags(existing)
    tt = (topic or "").strip()
    if tt and tt not in t:
        t.append(tt)
    return normalize_slip_tags(format_slip_tags(t, p, e))


def append_person(existing: str | None, person_name: str) -> str:
    t, p, e = parse_slip_tags(existing)
    pn = (person_name or "").strip()[:64]
    if pn and pn not in p:
        p.append(pn)
    return normalize_slip_tags(format_slip_tags(t, p, e))
