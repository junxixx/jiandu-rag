"""
将 bamboo_slips.tags 规范化为统一写法（英文逗号、人物统一为「人:姓名」、去重）。

在 backend 目录执行:
  python scripts/normalize_slip_tags_in_db.py
  python scripts/normalize_slip_tags_in_db.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
    override=True,
)

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import BambooSlip  # noqa: E402
from app.utils.slip_tags import normalize_slip_tags  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="规范化 bamboo_slips.tags")
    ap.add_argument("--dry-run", action="store_true", help="只统计不写库")
    args = ap.parse_args()
    os.environ.setdefault("SKIP_STARTUP_CHROMA_SYNC", "1")
    app = create_app()
    changed = 0
    with app.app_context():
        for row in BambooSlip.query.order_by(BambooSlip.id.asc()).yield_per(500):
            old = row.tags or ""
            new = normalize_slip_tags(row.tags)
            if new != old:
                changed += 1
                if not args.dry_run:
                    row.tags = new if new else None
        if not args.dry_run:
            db.session.commit()
    print(f"完成: 需更新 {changed} 条；dry_run={args.dry_run}")


if __name__ == "__main__":
    main()
