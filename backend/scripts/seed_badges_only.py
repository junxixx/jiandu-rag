"""已有库时单独补写徽章定义：python scripts/seed_badges_only.py"""
import os
import sys

_backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _backend)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_backend, ".env"), override=True)
os.environ.setdefault("SKIP_STARTUP_CHROMA_SYNC", "1")

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Badge  # noqa: E402


def main():
    app = create_app()
    with app.app_context():
        if Badge.query.first():
            print("徽章已存在，跳过。")
            return
        rows = [
            ("first_read", "初展牍", "首次将一枚简牍记入掌阅。", "Reading"),
            ("first_quiz", "日课首功", "首次答对每日简牍题目。", "CircleCheck"),
            ("reader_5", "展牍五通", "累计展读至少 5 枚不同简牍。", "Collection"),
            ("first_post", "雅集首帖", "在雅集论道发出首帖。", "EditPen"),
            ("debater", "辩场初试", "在辩论社完成首次驳难（需登录状态下）。", "ChatLineSquare"),
        ]
        for code, title, desc, icon in rows:
            db.session.add(Badge(code=code, title=title, description=desc, icon=icon))
        db.session.commit()
        print("已写入徽章 5 条。")


if __name__ == "__main__":
    main()
