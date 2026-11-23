"""
写入雅集默认话题（topics 表）。在 backend 目录执行:
  python scripts/seed_topics.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), override=True)

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Topic  # noqa: E402

DEFAULTS = [
    ("边塞生活", "戍卒禀食、烽燧值守与边塞日常文书"),
    ("书法艺术", "简牍书体、用笔与章法"),
    ("考古揭秘", "出土情境、整理与断代"),
    ("汉代历史", "制度、名物与历史背景"),
    ("读牍心得", "个人展卷笔记与问题"),
    ("文书制度", "官文书、玺印、行文书式与行政流程"),
    ("法律与爰书", "告劾、爰书、鞫讯与汉代司法用语"),
    ("名籍与算赋", "户籍、名数、赋役与乡里组织"),
    ("财政与物资", "赋税、仓储、物资调拨与度量衡"),
    ("民族与西域", "汉与匈奴、西域诸国及交通往来"),
    ("简牍整理", "缀合、释读、编号与数据库建设"),
    ("数字化与开放", "影像标准、元数据与学术共享"),
    ("比较视野", "与石刻、纸本及域外木牍的比较"),
    ("读书会", "共读材料、作业与讨论纪要"),
]


def main() -> None:
    app = create_app()
    with app.app_context():
        n = 0
        for name, desc in DEFAULTS:
            if Topic.query.filter_by(name=name).first():
                continue
            db.session.add(Topic(name=name, description=desc, hot=0, post_count=0))
            n += 1
        db.session.commit()
        print(f"新增话题 {n} 条（已存在则跳过）")


if __name__ == "__main__":
    main()
