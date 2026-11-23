from sqlalchemy import func

from app.extensions import db
from app.models import Badge, Post, UserBadge, UserQuizAttempt, UserSlipProgress


def _award(user_id: int, code: str) -> bool:
    b = Badge.query.filter_by(code=code).first()
    if not b:
        return False
    if UserBadge.query.filter_by(user_id=user_id, badge_id=b.id).first():
        return False
    db.session.add(UserBadge(user_id=user_id, badge_id=b.id))
    db.session.commit()
    return True


def after_slip_progress(user_id: int) -> None:
    n = UserSlipProgress.query.filter_by(user_id=user_id).count()
    if n == 1:
        _award(user_id, "first_read")
    distinct = (
        db.session.query(func.count(func.distinct(UserSlipProgress.slip_id)))
        .filter(UserSlipProgress.user_id == user_id)
        .scalar()
    )
    if (distinct or 0) >= 5:
        _award(user_id, "reader_5")


def after_quiz_correct(user_id: int) -> None:
    n = (
        UserQuizAttempt.query.filter_by(user_id=user_id, is_correct=True).count()
    )
    if n == 1:
        _award(user_id, "first_quiz")


def after_first_post(user_id: int) -> None:
    n = Post.query.filter_by(user_id=user_id).count()
    if n == 1:
        _award(user_id, "first_post")


def after_debate(user_id: int) -> None:
    _award(user_id, "debater")
