"""基于共现的 ItemCF，结果写入 Redis key itemcf:similar:{slip_id}（TTL 1h）。"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from typing import Any, Dict, List

import redis
from flask import current_app

from app.extensions import db
from app.models import UserSlipProgress

_last_warm: Dict[str, float] = {}
_WARM_INTERVAL_SEC = 300


def _redis() -> redis.Redis | None:
    try:
        return redis.from_url(
            current_app.config.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
            decode_responses=True,
        )
    except Exception:
        return None


def warm_itemcf_cache() -> Dict[str, Any]:
    """按用户共现简牍统计相似度，写入 Redis。"""
    r = _redis()
    if not r:
        return {"ok": False, "reason": "no_redis"}
    user_slips: dict[int, set[int]] = defaultdict(set)
    rows = UserSlipProgress.query.all()
    for row in rows:
        user_slips[row.user_id].add(row.slip_id)
    co: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for _uid, slips in user_slips.items():
        lst = list(slips)
        for i, a in enumerate(lst):
            for b in lst[i + 1 :]:
                co[a][b] += 1
                co[b][a] += 1
    n = 0
    for sid, counter in co.items():
        top = sorted(counter.items(), key=lambda x: -x[1])[:15]
        key = f"itemcf:similar:{sid}"
        r.set(key, json.dumps([b for b, _ in top]), ex=3600)
        n += 1
    return {"ok": True, "keys_written": n}


def maybe_warm_itemcf() -> None:
    global _last_warm
    rid = str(id(current_app))
    now = time.time()
    if now - _last_warm.get(rid, 0) < _WARM_INTERVAL_SEC:
        return
    _last_warm[rid] = now
    try:
        warm_itemcf_cache()
    except Exception:
        pass


def similar_slip_ids(slip_id: int, limit: int = 10) -> List[int]:
    r = _redis()
    if not r:
        return []
    raw = r.get(f"itemcf:similar:{slip_id}")
    if not raw:
        return []
    try:
        arr = json.loads(raw)
        return [int(x) for x in arr[:limit]]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
