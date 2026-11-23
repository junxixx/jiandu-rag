"""
戍边手记（Quest）任务模板：与前端 QuestLogView 三步线对应。
可重复执行，已存在相同 code 则跳过。

用法（backend 目录）:
  python scripts/seed_quest_templates.py
"""
from __future__ import annotations

import os
import sys

_backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _backend)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_backend, ".env"), override=True)
os.environ.setdefault("SKIP_STARTUP_CHROMA_SYNC", "1")

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import TaskTemplate  # noqa: E402

QUEST_TASKS = [
    ("quest_daily_slip", "戍边日志·每日一牍", 5),
    ("quest_night_chat", "戍边日志·边塞夜话", 5),
    ("quest_forum_post", "戍边日志·雅集留痕", 5),
]


def main() -> None:
    app = create_app()
    with app.app_context():
        added = 0
        for code, title, pts in QUEST_TASKS:
            if TaskTemplate.query.filter_by(code=code).first():
                continue
            db.session.add(TaskTemplate(code=code, title=title, points_reward=pts))
            added += 1
        if added:
            db.session.commit()
        print(f"完成：新增 {added} 条任务模板（跳过已存在）。")


if __name__ == "__main__":
    main()
