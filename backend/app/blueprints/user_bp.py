from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from app.constants import POINTS_CHECKIN_BASE, POINTS_READ_SLIP, STREAK_BONUS_MULTIPLIER
from app.constants import STREAK_BONUS_MULTIPLIER_DAYS
from app.extensions import db
from app.models import (
    Comment,
    Post,
    User,
    UserBadge,
    UserCheckin,
    UserQuizAttempt,
    UserSlipProgress,
)
from app.services import streak_service as streak_svc
import secrets
bp = Blueprint("user", __name__)


def _current_user():
    uid = int(get_jwt_identity())
    return User.query.get(uid)


@bp.get("/me")
@jwt_required()
def me():
    u = _current_user()
    if not u:
        return jsonify({"error": "用户不存在"}), 404
    return jsonify(
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "nickname": u.nickname,
            "avatar_url": u.avatar_url,
            "points": u.points,
            "invite_code": getattr(u, "invite_code", None),
        }
    )


@bp.post("/invite-code")
@jwt_required()
def ensure_invite_code():
    """为历史用户补发邀请码（注册时已生成；老数据可能为空）。"""
    u = _current_user()
    if not u:
        return jsonify({"error": "用户不存在"}), 404
    if getattr(u, "invite_code", None):
        return jsonify({"ok": True, "invite_code": u.invite_code})
    for _ in range(16):
        code = secrets.token_hex(3).upper()[:8]
        if not User.query.filter_by(invite_code=code).first():
            u.invite_code = code
            db.session.commit()
            return jsonify({"ok": True, "invite_code": u.invite_code})
    return jsonify({"error": "邀请码生成失败，请稍后重试"}), 500


@bp.patch("/profile")
@jwt_required()
def profile():
    u = _current_user()
    if not u:
        return jsonify({"error": "用户不存在"}), 404
    data = request.get_json(silent=True) or {}
    if "nickname" in data and data["nickname"]:
        u.nickname = str(data["nickname"])[:64]
    if "avatar_url" in data:
        u.avatar_url = (data.get("avatar_url") or None) and str(data["avatar_url"])[:512]
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/progress/read")
@jwt_required()
def mark_read():
    u = _current_user()
    if not u:
        return jsonify({"error": "用户不存在"}), 404
    data = request.get_json(silent=True) or {}
    slip_id = data.get("slip_id")
    if slip_id is None:
        return jsonify({"error": "slip_id 必填"}), 400
    sid = int(slip_id)
    ex = UserSlipProgress.query.filter_by(user_id=u.id, slip_id=sid).first()
    pts = 0
    if not ex:
        db.session.add(UserSlipProgress(user_id=u.id, slip_id=sid))
        u.points = (u.points or 0) + POINTS_READ_SLIP
        pts = POINTS_READ_SLIP
    db.session.commit()
    from app.services import badge_service as bs

    bs.after_slip_progress(u.id)
    return jsonify({"ok": True, "points_delta": pts})


@bp.post("/checkin")
@jwt_required()
def checkin():
    u = _current_user()
    if not u:
        return jsonify({"error": "用户不存在"}), 404
    today = date.today()
    if UserCheckin.query.filter_by(user_id=u.id, checkin_date=today).first():
        st = streak_svc.checkin_streak_days(u.id)
        return jsonify({"ok": True, "already": True, "streak_days": st})
    db.session.add(UserCheckin(user_id=u.id, checkin_date=today))
    db.session.commit()
    st = streak_svc.checkin_streak_days(u.id)
    bonus = st > 0 and st % STREAK_BONUS_MULTIPLIER_DAYS == 0
    pts = int(POINTS_CHECKIN_BASE * (STREAK_BONUS_MULTIPLIER if bonus else 1.0))
    u.points = (u.points or 0) + pts
    db.session.commit()
    return jsonify({"ok": True, "streak_days": st, "points_delta": pts, "milestone_bonus": bonus})


@bp.get("/learning-map")
@jwt_required()
def learning_map():
    u = _current_user()
    if not u:
        return jsonify({"error": "用户不存在"}), 404
    uid = u.id
    reads = UserSlipProgress.query.filter_by(user_id=uid).count()
    quiz_total = UserQuizAttempt.query.filter_by(user_id=uid).count()
    quiz_ok = UserQuizAttempt.query.filter_by(user_id=uid, is_correct=True).count()
    posts_n = Post.query.filter_by(user_id=uid).count()
    comments_n = Comment.query.filter_by(user_id=uid).count()
    badges_n = UserBadge.query.filter_by(user_id=uid).count()
    rate = (quiz_ok / quiz_total) if quiz_total else 0.0
    # 雷达维度 0–100（学习地图可视化）
    dim_read = min(100, reads * 3)
    dim_quiz = min(100, int(rate * 100))
    dim_social = min(100, (posts_n + comments_n) * 8)
    dim_badges = min(100, badges_n * 20)
    dim_streak = min(100, streak_svc.checkin_streak_days(uid) * 12)
    return jsonify(
        {
            "stats": {
                "slips_read": reads,
                "quiz_attempts": quiz_total,
                "quiz_correct": quiz_ok,
                "quiz_accuracy": round(rate, 4),
                "posts": posts_n,
                "comments": comments_n,
                "badges": badges_n,
                "checkin_streak": streak_svc.checkin_streak_days(uid),
            },
            "radar": {
                "dimensions": ["读牍", "问答", "雅集", "徽章", "打卡"],
                "values": [dim_read, dim_quiz, dim_social, dim_badges, dim_streak],
            },
        }
    )


@bp.get("/badges")
@jwt_required()
def badges():
    u = _current_user()
    if not u:
        return jsonify({"error": "用户不存在"}), 404
    rows = (
        UserBadge.query.filter_by(user_id=u.id)
        .order_by(UserBadge.created_at.desc())
        .all()
    )
    return jsonify(
        {
            "items": [
                {
                    "code": x.badge.code,
                    "title": x.badge.title,
                    "description": x.badge.description,
                    "icon": x.badge.icon,
                    "at": x.created_at.isoformat(),
                }
                for x in rows
            ]
        }
    )


@bp.get("/progress")
@jwt_required()
def progress():
    u = _current_user()
    if not u:
        return jsonify({"error": "用户不存在"}), 404
    rows = UserSlipProgress.query.filter_by(user_id=u.id).order_by(UserSlipProgress.read_at.desc()).limit(50).all()
    return jsonify(
        {
            "items": [
                {"slip_id": r.slip_id, "read_at": r.read_at.isoformat()}
                for r in rows
            ]
        }
    )
