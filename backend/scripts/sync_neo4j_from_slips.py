"""
将 MySQL bamboo_slips 同步到 Neo4j（Slip / Tag / Person / Site 最小子图）。

用法（backend 目录，已配置 .env 与 Neo4j）:
  python scripts/sync_neo4j_from_slips.py              # 单次最多 500 条
  python scripts/sync_neo4j_from_slips.py 1000
  python scripts/sync_neo4j_from_slips.py --all        # 全库分批（上线推荐）

人物标签约定：在 tags 中使用「人:姓名」或「人物:姓名」（半角或全角冒号均可）。
解析/格式化逻辑见 app.utils.slip_tags；可执行 python scripts/normalize_slip_tags_in_db.py 统一库内写法。
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path=_env, override=True)

from app import create_app  # noqa: E402
from app.services import neo4j_service as neo  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="MySQL bamboo_slips → Neo4j")
    ap.add_argument(
        "limit",
        nargs="?",
        type=int,
        default=500,
        help="单次同步条数（1～50000）；与 --all 互斥",
    )
    ap.add_argument("--all", action="store_true", help="全量同步（分批，MERGE 幂等）")
    args = ap.parse_args()

    os.environ.setdefault("SKIP_STARTUP_CHROMA_SYNC", "1")
    app = create_app()
    with app.app_context():
        if args.all:
            r = neo.sync_bamboo_slips_full_from_mysql()
        else:
            if args.limit is not None and args.limit <= 0:
                print("limit 须为正整数；全量请使用 --all")
                sys.exit(2)
            r = neo.sync_bamboo_slips_from_mysql(limit=max(1, min(args.limit, 50_000)))
        print(r)


if __name__ == "__main__":
    main()
