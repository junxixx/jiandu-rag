from datetime import date, timedelta

from app.extensions import db
from app.models import UserCheckin


def checkin_streak_days(user_id: int) -> int:
    """从今天起连续有打卡记录的天数。"""
    rows = (
        UserCheckin.query.filter_by(user_id=user_id)
        .order_by(UserCheckin.checkin_date.desc())
        .limit(400)
        .all()
    )
    if not rows:
        return 0
    have = {r.checkin_date for r in rows}
    streak = 0
    d = date.today()
    while d in have:
        streak += 1
        d = d - timedelta(days=1)
    return streak
