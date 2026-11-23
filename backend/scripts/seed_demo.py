"""
演示数据：≥30 枚简牍、每日简牍、任务模板。
用法（在 backend 目录）:
  pip install -r requirements.txt
  先创建库: mysql < scripts/create_db.sql
  python scripts/seed_demo.py
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta

_backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _backend)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_backend, ".env"), override=True)
os.environ.setdefault("SKIP_STARTUP_CHROMA_SYNC", "1")

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import (  # noqa: E402
    Badge,
    BambooSlip,
    DailySlip,
    TaskTemplate,
)
from app.utils.slip_tags import format_slip_tags  # noqa: E402


def _seed_badges():
    if Badge.query.first():
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
    print("已写入徽章定义 5 条。")


def main():
    app = create_app()
    with app.app_context():
        _seed_badges()
        if BambooSlip.query.first():
            print("已有简牍数据，跳过写入。")
            print(
                "若「每日一牍 / 雅集 / 边塞夜话」仍空：请先注册一用户，再执行\n"
                "  SKIP_STARTUP_CHROMA_SYNC=1 python scripts/bootstrap_module_content.py"
            )
            return

        sites = ["居延", "敦煌", "武威", "长沙", "龙岗寺"]
        templates = [
            ("禀食记录", "某月某日卒某禀黍米若干", "这是戍卒领取口粮的记录，反映边塞后勤。"),
            ("候长文书", "候长某谓士吏某", "基层军官之间的行政往来文书。"),
            ("爰书片段", "谨验问某辞曰", "司法调查中的供辞记录。"),
            ("吏卒名册", "卒某年廿某居某里", "名籍类简牍，用于征发与戍守管理。"),
            ("烽火品约", "虏犯塞举烽如品", "边塞报警制度的条文摘录。"),
        ]

        slips: list[BambooSlip] = []
        for i in range(1, 31):
            t_idx = (i - 1) % len(templates)
            title_t, trans_t, vern_t = templates[t_idx]
            site = sites[(i - 1) % len(sites)]
            if i == 1:
                persons = ["李敢"]
            elif i == 5:
                persons = ["张安世"]
            elif i == 12:
                persons = ["终军"]
            else:
                persons = []
            slip = BambooSlip(
                code=f"DJ-{i:03d}",
                title=f"{title_t}（示例 {i}）",
                image_url=f"/static/slips/dj{i:03d}.jpg",
                transcription=f"{trans_t} · 编号{i}，出土于{site}相关批次。",
                vernacular=f"{vern_t} 本条为平台演示数据，正式环境请替换为可靠释文与白话。",
                site_name=site,
                era="西汉晚期至东汉",
                tags=format_slip_tags(["演示", "边塞", "文书"], persons),
            )
            slips.append(slip)
            db.session.add(slip)
        db.session.flush()

        today = date.today()
        first = slips[0]
        daily = DailySlip(
            slip_id=first.id,
            feature_date=today,
            quiz_question="「禀食」类简牍主要反映以下哪类事务？",
            quiz_options=["军事训练", "口粮发放", "祭祀活动", "商业贸易"],
            correct_index=1,
        )
        db.session.add(daily)
        db.session.add(
            DailySlip(
                slip_id=slips[1].id,
                feature_date=today - timedelta(days=1),
                quiz_question="「爰书」与下列哪项最接近？",
                quiz_options=["诗歌", "司法供辞", "地图", "医方"],
                correct_index=1,
            )
        )

        for code, title, pts in [
            ("read_daily", "阅读今日简牍", 5),
            ("share_card", "分享简牍卡片", 8),
            ("quiz_ok", "完成每日答题", 10),
            ("check_in", "学习打卡", 3),
        ]:
            db.session.add(TaskTemplate(code=code, title=title, points_reward=pts))

        db.session.commit()

        from app.services.rag_service import sync_slips_to_chroma_if_possible

        sync_slips_to_chroma_if_possible()
        print("已写入 30 枚演示简牍、2 日每日简牍、4 个任务模板，并已尝试同步 Chroma。")


if __name__ == "__main__":
    main()
