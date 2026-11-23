from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.constants import (
    POINTS_QUIZ_CORRECT,
    STREAK_BONUS_MULTIPLIER,
    STREAK_BONUS_MULTIPLIER_DAYS,
)
from app.extensions import db
from app.models import DailySlip, User, UserQuizAttempt, UserSlipProgress
from app.services import streak_service as streak_svc

bp = Blueprint("daily_slip", __name__)


def _quizzes_public(row: DailySlip) -> list[dict]:
    did = int(row.id)
    if row.quizzes_json and isinstance(row.quizzes_json, list) and len(row.quizzes_json) >= 1:
        out = []
        for i, q in enumerate(row.quizzes_json[:3]):
            if not isinstance(q, dict):
                continue
            out.append(
                {
                    "quiz_index": i,
                    "daily_slip_id": did,
                    "question": q.get("question", ""),
                    "options": q.get("options") or [],
                }
            )
        if out:
            return out
    return [
        {
            "quiz_index": 0,
            "daily_slip_id": did,
            "question": row.quiz_question,
            "options": row.quiz_options,
        }
    ]


def _correct_index(row: DailySlip, quiz_index: int) -> int:
    if row.quizzes_json and isinstance(row.quizzes_json, list) and 0 <= quiz_index < len(row.quizzes_json):
        q = row.quizzes_json[quiz_index]
        if isinstance(q, dict) and "correct_index" in q:
            return int(q["correct_index"])
    return int(row.correct_index)


@bp.get("/today")
@jwt_required(optional=True)
def today():
    d = date.today()
    row = DailySlip.query.filter_by(feature_date=d).first()
    if not row:
        row = DailySlip.query.order_by(DailySlip.feature_date.desc()).first()
    if not row:
        return jsonify({"error": "尚未配置每日简牍"}), 404
    s = row.slip
    qlist = _quizzes_public(row)
    return jsonify(
        {
            "date": row.feature_date.isoformat(),
            "daily_slip_id": row.id,
            "slip": {
                "id": s.id,
                "code": s.code,
                "title": s.title,
                "image_url": s.image_url,
                "transcription": s.transcription,
                "vernacular": s.vernacular,
                "site_name": s.site_name,
                "era": s.era,
            },
            "fun_fact": getattr(row, "fun_fact", None) or None,
            "quizzes": qlist,
            # 兼容旧前端：首题结构
            "quiz": qlist[0] if qlist else None,
        }
    )


@bp.post("/answer")
@jwt_required()
def answer():
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    daily_slip_id = data.get("daily_slip_id")
    choice = data.get("choice_index")
    quiz_index = int(data.get("quiz_index") or 0)
    if daily_slip_id is None or choice is None:
        return jsonify({"error": "缺少 daily_slip_id 或 choice_index"}), 400
    row = DailySlip.query.get(daily_slip_id)
    if not row:
        return jsonify({"error": "题目不存在"}), 404
    correct_idx = _correct_index(row, quiz_index)
    ok = int(choice) == int(correct_idx)
    log = UserQuizAttempt(
        user_id=uid,
        daily_slip_id=row.id,
        choice_index=int(choice),
        quiz_index=quiz_index,
        is_correct=ok,
    )
    db.session.add(log)
    streak = streak_svc.checkin_streak_days(uid)
    mult = (
        STREAK_BONUS_MULTIPLIER
        if streak >= STREAK_BONUS_MULTIPLIER_DAYS
        else 1.0
    )
    points_delta = 0
    if ok:
        u = User.query.get(uid)
        if u:
            points_delta = int(POINTS_QUIZ_CORRECT * mult)
            u.points = (u.points or 0) + points_delta
    db.session.add(UserSlipProgress(user_id=uid, slip_id=row.slip_id))
    db.session.commit()
    try:
        from app.services import badge_service as bs

        bs.after_slip_progress(uid)
        if ok:
            bs.after_quiz_correct(uid)
    except Exception:
        pass
    return jsonify(
        {
            "correct": ok,
            "points_delta": points_delta,
            "streak_days": streak,
            "streak_multiplier_applied": mult > 1,
        }
    )
