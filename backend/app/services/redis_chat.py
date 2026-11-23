import json
from typing import List, Tuple

import redis
from flask import current_app


def _client() -> redis.Redis | None:
    try:
        url = current_app.config.get("REDIS_URL", "redis://127.0.0.1:6379/0")
        return redis.from_url(url, decode_responses=True)
    except Exception:
        return None


def append_turn(
    session_key: str,
    role: str,
    content: str,
    max_turns: int = 12,
    user_id: int | None = None,
    role_key: str | None = None,
) -> None:
    r = _client()
    if not r:
        return
    key = f"chat:ctx:{session_key}"
    item = json.dumps({"role": role, "content": content}, ensure_ascii=False)
    r.rpush(key, item)
    r.ltrim(key, -max_turns, -1)
    r.expire(key, 86400 * 7)
    # 说明书命名：chat:short:{user_id}:{character_id}，TTL 30 分钟
    if user_id is not None and role_key:
        sk = f"chat:short:{user_id}:{role_key}"
        r.rpush(sk, item)
        r.ltrim(sk, -max_turns, -1)
        r.expire(sk, 1800)


def recent_turns(session_key: str, limit: int = 8) -> List[Tuple[str, str]]:
    r = _client()
    if not r:
        return []
    key = f"chat:ctx:{session_key}"
    raw = r.lrange(key, -limit, -1)
    out: List[Tuple[str, str]] = []
    for x in raw:
        try:
            o = json.loads(x)
            out.append((o.get("role", "user"), o.get("content", "")))
        except Exception:
            continue
    return out
