"""
按 bamboo_slips.code 将 title 规范为「简牍 {code}」。

默认只处理疑似旧版标题（含数据集名或「简牍 · train/…」等）；
加 --all 则每条简牍都重写标题（慎用：会覆盖你已手工改过的标题）。

用法（backend 目录）:
  python scripts/refresh_slip_titles_from_codes.py --dry-run
  python scripts/refresh_slip_titles_from_codes.py
  python scripts/refresh_slip_titles_from_codes.py --all
"""
from __future__ import annotations

import argparse
import os
import re
import sys

_backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _backend)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_backend, ".env"), override=True)
os.environ.setdefault("SKIP_STARTUP_CHROMA_SYNC", "1")

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import BambooSlip  # noqa: E402

_SPLIT_PATH = re.compile(r"\s*·\s*(train|val|test)/", re.I)


def _needs_default_refresh(title: str | None, code: str) -> bool:
    """是否像旧导入脚本生成的标题，值得自动改。"""
    t = (title or "").strip()
    if not t:
        return True
    low = t.lower()
    if "deepjiandu" in low.replace(" ", ""):
        return True
    if _SPLIT_PATH.search(t):
        return True
    expected = f"简牍 {code}"
    if t == expected:
        return False
    if t.startswith("简牍 ") and not t.startswith(expected):
        return False
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="将简牍 title 规范为「简牍 {code}」")
    ap.add_argument("--dry-run", action="store_true", help="只打印不提交")
    ap.add_argument(
        "--all",
        action="store_true",
        help="全部重写为「简牍 {code}」（覆盖已有标题）",
    )
    args = ap.parse_args()

    app = create_app()
    touched = 0
    with app.app_context():
        for row in BambooSlip.query.order_by(BambooSlip.id.asc()).all():
            code = (row.code or "").strip()
            if not code:
                continue
            new_title = f"简牍 {code}"
            if not args.all:
                if not _needs_default_refresh(row.title, code):
                    continue
            if (row.title or "").strip() == new_title:
                continue
            if args.dry_run:
                print(f"[dry-run] id={row.id} code={code!r} {row.title!r} -> {new_title!r}")
            else:
                row.title = new_title
            touched += 1
        if not args.dry_run and touched:
            db.session.commit()
    print(f"{'[dry-run] ' if args.dry_run else ''}更新 {touched} 条 title")


if __name__ == "__main__":
    main()
