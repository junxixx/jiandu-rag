from datetime import date, datetime, timedelta
from functools import wraps

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func

from app.extensions import db
from app.models import AnalyticsEvent, DailySlip, Post
from app.services import site_config as sc

bp = Blueprint("admin", __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = (current_app.config.get("ADMIN_TOKEN") or "").strip()
        if not token:
            return jsonify({"error": "未配置 ADMIN_TOKEN，管理端未启用"}), 503
        if request.headers.get("X-Admin-Token", "").strip() != token:
            return jsonify({"error": "无权访问"}), 403
        return f(*args, **kwargs)

    return decorated


@bp.get("/analytics/summary")
@admin_required
def analytics_summary():
    days = min(max(int(request.args.get("days", 7)), 1), 90)
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.session.query(AnalyticsEvent.event_type, func.count(AnalyticsEvent.id))
        .filter(AnalyticsEvent.created_at >= since)
        .group_by(AnalyticsEvent.event_type)
        .all()
    )
    return jsonify(
        {
            "days": days,
            "since": since.isoformat() + "Z",
            "counts": {r[0]: r[1] for r in rows},
        }
    )


@bp.get("/kv/<key>")
@admin_required
def get_kv(key):
    if key not in ("blocked_words", "debate_topics"):
        return jsonify({"error": "未知 key"}), 400
    return jsonify({"key": key, "value": sc.get_kv(key)})


@bp.put("/kv/<key>")
@admin_required
def put_kv(key):
    if key not in ("blocked_words", "debate_topics"):
        return jsonify({"error": "未知 key"}), 400
    data = request.get_json(silent=True)
    if data is None or "value" not in data:
        return jsonify({"error": "需要 JSON { value: ... }"}), 400
    sc.set_kv(key, data["value"])
    return jsonify({"ok": True})


@bp.post("/daily")
@admin_required
def set_daily():
    data = request.get_json(silent=True) or {}
    try:
        slip_id = int(data["slip_id"])
        d = date.fromisoformat(str(data["feature_date"]))
    except Exception:
        return jsonify({"error": "需要 slip_id 与 feature_date(YYYY-MM-DD)"}), 400
    row = DailySlip.query.filter_by(feature_date=d).first()
    qq = data.get("quiz_question")
    qo = data.get("quiz_options")
    ci = data.get("correct_index")
    if row:
        row.slip_id = slip_id
        if qq:
            row.quiz_question = str(qq)[:512]
        if qo is not None:
            row.quiz_options = qo
        if ci is not None:
            row.correct_index = int(ci)
        if "fun_fact" in data:
            row.fun_fact = data.get("fun_fact")
        if "quizzes_json" in data:
            row.quizzes_json = data.get("quizzes_json")
    else:
        if not qq or qo is None or ci is None:
            return jsonify(
                {"error": "新建每日简牍须提供 quiz_question、quiz_options、correct_index"}
            ), 400
        row = DailySlip(
            slip_id=slip_id,
            feature_date=d,
            quiz_question=str(qq)[:512],
            quiz_options=qo,
            correct_index=int(ci),
            fun_fact=data.get("fun_fact"),
            quizzes_json=data.get("quizzes_json"),
        )
        db.session.add(row)
    db.session.commit()
    return jsonify({"ok": True, "daily_slip_id": row.id})


@bp.get("/posts/pending")
@admin_required
def posts_pending():
    rows = (
        Post.query.filter(Post.status.in_(("pending", "blocked")))
        .order_by(Post.created_at.desc())
        .limit(100)
        .all()
    )
    return jsonify(
        {
            "items": [
                {
                    "id": p.id,
                    "title": p.title,
                    "status": p.status,
                    "risk_score": p.risk_score,
                    "author_id": p.user_id,
                    "created_at": p.created_at.isoformat(),
                }
                for p in rows
            ]
        }
    )


@bp.patch("/posts/<int:pid>/moderate")
@admin_required
def moderate_post(pid):
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip().lower()
    if status not in ("published", "blocked", "pending"):
        return jsonify({"error": "status 须为 published / blocked / pending"}), 400
    p = Post.query.get(pid)
    if not p:
        return jsonify({"error": "帖子不存在"}), 404
    p.status = status
    db.session.commit()
    return jsonify({"ok": True, "id": p.id, "status": p.status})


@bp.post("/graph/sync-neo4j")
@admin_required
def sync_neo4j():
    """从 MySQL bamboo_slips 同步标签/人物/遗址到 Neo4j（MERGE，可重复执行）。
    JSON: { "full": true } 全量分批同步；或 { "limit": 500 } 单次最多条数（1～50000）。
    """
    data = request.get_json(silent=True) or {}
    from app.services import neo4j_service as neo

    if data.get("full") is True:
        r = neo.sync_bamboo_slips_full_from_mysql()
    else:
        try:
            limit = int(data.get("limit", 500))
        except (TypeError, ValueError):
            limit = 500
        r = neo.sync_bamboo_slips_from_mysql(limit=limit)
    return jsonify(r), (200 if r.get("ok") else 500)
