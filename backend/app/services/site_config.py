import json
from typing import Any, List

from app.extensions import db
from app.models import SiteKV


def get_kv(key: str, default: Any = None) -> Any:
    row = SiteKV.query.get(key)
    if not row or row.value is None:
        return default
    try:
        return json.loads(row.value)
    except Exception:
        return default


def set_kv(key: str, value: Any) -> None:
    row = SiteKV.query.get(key)
    s = json.dumps(value, ensure_ascii=False)
    if row:
        row.value = s
    else:
        db.session.add(SiteKV(key=key, value=s))
    db.session.commit()


def get_extra_blocked_words() -> List[str]:
    v = get_kv("blocked_words", [])
    if isinstance(v, list):
        return [str(x) for x in v if x]
    return []


def get_debate_topics() -> List[str]:
    v = get_kv("debate_topics", [])
    if isinstance(v, list):
        return [str(x) for x in v if x]
    return []
