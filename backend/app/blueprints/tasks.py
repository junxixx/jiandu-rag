from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models import TaskTemplate, User, UserTaskLog

bp = Blueprint("tasks", __name__)


@bp.get("/daily")
@jwt_required()
def daily_tasks():
    templates = TaskTemplate.query.all()
    uid = int(get_jwt_identity())
    today = date.today()
    done_codes = {
        r.task_code
        for r in UserTaskLog.query.filter_by(user_id=uid, log_date=today).all()
    }
    return jsonify(
        {
            "date": today.isoformat(),
            "items": [
                {
                    "code": t.code,
                    "title": t.title,
                    "points_reward": t.points_reward,
                    "completed": t.code in done_codes,
                }
                for t in templates
            ],
        }
    )


@bp.post("/complete")
@jwt_required()
def complete():
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    code = (data.get("task_code") or "").strip()
    if not code:
        return jsonify({"error": "task_code 必填"}), 400
    t = TaskTemplate.query.filter_by(code=code).first()
    if not t:
        return jsonify({"error": "任务不存在"}), 404
    today = date.today()
    ex = UserTaskLog.query.filter_by(user_id=uid, task_code=code, log_date=today).first()
    if ex:
        return jsonify({"ok": True, "already": True, "points": 0})
    db.session.add(UserTaskLog(user_id=uid, task_code=code, log_date=today))
    u = User.query.get(uid)
    if u:
        u.points = (u.points or 0) + t.points_reward
    db.session.commit()
    return jsonify({"ok": True, "points_delta": t.points_reward})
