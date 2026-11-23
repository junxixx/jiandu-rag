"""
将 bamboo_slips 中占位出土地清空（如曾误写入数据集名）。

用法（backend 目录）:
  python scripts/clear_placeholder_sites.py
  python scripts/clear_placeholder_sites.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys

_backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _backend)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_backend, ".env"), override=True)
os.environ.setdefault("SKIP_STARTUP_CHROMA_SYNC", "1")

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import BambooSlip  # noqa: E402

def _is_placeholder_site(sn: str) -> bool:
    t = sn.strip().lower().replace(" ", "")
    return bool(t) and ("deepjiandu" in t or t in {"dj", "dataset"})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    app = create_app()
    n = 0
    with app.app_context():
        for row in BambooSlip.query.all():
            sn = (row.site_name or "").strip()
            if not sn:
                continue
            if _is_placeholder_site(sn):
                if args.dry_run:
                    print(f"would clear id={row.id} code={row.code!r} site_name={sn!r}")
                else:
                    row.site_name = None
                n += 1
        if not args.dry_run and n:
            db.session.commit()
    print(f"{'[dry-run] ' if args.dry_run else ''}处理 {n} 条出土地占位")


if __name__ == "__main__":
    main()
