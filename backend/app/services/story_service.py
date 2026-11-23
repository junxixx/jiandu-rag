"""剧情进度：Redis Hash story:progress:{user_id}（说明书 story:progress）。"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import redis
from flask import current_app

STORY_ID = "shubian_log"
NODES: List[Dict[str, Any]] = [
    {
        "id": "n1",
        "title": "戍边日志 · 序",
        "body": "边塞木牍上的墨迹，是两千年前某个戍卒的一天。读完今日简牍，仿佛替他记下一行。",
        "reward": 5,
        "next": ["n2"],
    },
    {
        "id": "n2",
        "title": "日课一题",
        "body": "在「每日一牍」答对一题，验一验释读是否入心。",
        "reward": 10,
        "next": ["n3"],
    },
    {
        "id": "n3",
        "title": "夜话烽燧",
        "body": "在边塞夜话任选人物对谈一回，把纸上的字变成耳边风。",
        "reward": 10,
        "next": [],
    },
]


def _r() -> redis.Redis | None:
    try:
        return redis.from_url(
            current_app.config.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
            decode_responses=True,
        )
    except Exception:
        return None


def _key(uid: int) -> str:
    return f"story:progress:{uid}"


def get_progress(user_id: int) -> Dict[str, Any]:
    r = _r()
    if not r:
        return _default_progress()
    h = r.hgetall(_key(user_id))
    if not h:
        return _default_progress()
    try:
        completed = json.loads(h.get("completed_nodes") or "[]")
    except json.JSONDecodeError:
        completed = []
    return {
        "story_id": h.get("story_id") or STORY_ID,
        "current_node": h.get("current_node") or NODES[0]["id"],
        "completed_nodes": completed,
        "rewards_total": int(h.get("rewards_total") or 0),
        "nodes": NODES,
    }


def _default_progress() -> Dict[str, Any]:
    return {
        "story_id": STORY_ID,
        "current_node": NODES[0]["id"],
        "completed_nodes": [],
        "rewards_total": 0,
        "nodes": NODES,
    }


def advance(user_id: int, target_node_id: str) -> Dict[str, Any]:
    """从当前节点推进到合法下一节点。"""
    r = _r()
    prog = get_progress(user_id)
    cur = prog["current_node"]
    completed = list(prog["completed_nodes"])
    rewards = int(prog["rewards_total"])
    node_map = {n["id"]: n for n in NODES}
    if cur not in node_map:
        cur = NODES[0]["id"]
    current = node_map[cur]
    if target_node_id == cur:
        return {
            "ok": True,
            "current_node": cur,
            "completed_nodes": completed,
            "rewards_total": rewards,
            "points_delta": 0,
            "nodes": NODES,
        }
    if target_node_id not in current.get("next", []):
        return {"ok": False, "error": "无效的剧情推进"}
    points_delta = 0
    if cur not in completed:
        completed.append(cur)
        points_delta = int(current.get("reward") or 0)
        rewards += points_delta
    new_current = target_node_id
    if r:
        key = _key(user_id)
        # 逐字段 HSET，兼容 Redis 3.x（mapping= 多对一命令需 Redis 4+）
        fields = {
            "story_id": STORY_ID,
            "current_node": new_current,
            "completed_nodes": json.dumps(completed, ensure_ascii=False),
            "rewards_total": str(rewards),
        }
        for fname, fval in fields.items():
            r.hset(key, fname, fval)
        r.expire(key, 86400 * 14)
    return {
        "ok": True,
        "current_node": new_current,
        "completed_nodes": completed,
        "rewards_total": rewards,
        "points_delta": points_delta,
        "nodes": NODES,
    }
