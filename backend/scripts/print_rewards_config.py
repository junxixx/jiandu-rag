"""
打印当前积分常量（含 .env 覆盖）与库内任务模板，供「积分/任务/徽章」定稿核对。

用法（backend 目录）:
  python scripts/print_rewards_config.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), override=True)

os.environ.setdefault("SKIP_STARTUP_CHROMA_SYNC", "1")

from app import create_app  # noqa: E402
import app.constants as C  # noqa: E402
from app.models import Badge, TaskTemplate  # noqa: E402


def main() -> None:
    app = create_app()
    print("—— 积分与环境（app.constants / .env）——")
    for name in (
        "POINTS_READ_SLIP",
        "POINTS_SHARE_CARD",
        "POINTS_QUIZ_CORRECT",
        "POINTS_POST_LIKE",
        "POINTS_INVITE_REFERRER",
        "POINTS_INVITE_NEWUSER",
        "POINTS_CHECKIN_BASE",
        "STREAK_BONUS_MULTIPLIER_DAYS",
        "STREAK_BONUS_MULTIPLIER",
        "AI_MODERATION_BLOCK",
        "AI_MODERATION_PENDING",
    ):
        print(f"  {name} = {getattr(C, name)}")

    with app.app_context():
        print("\n—— 任务模板（task_templates）——")
        for r in TaskTemplate.query.order_by(TaskTemplate.id.asc()).all():
            print(f"  {r.code}\t{r.title}\t{r.points_reward} 分")

        print("\n—— 徽章（badges）——")
        rows = Badge.query.order_by(Badge.id.asc()).all()
        if not rows:
            print("  （空，可运行 python scripts/seed_badges_only.py）")
        else:
            for r in rows:
                print(f"  {r.code}\t{r.title}\t{r.description}")


if __name__ == "__main__":
    main()
