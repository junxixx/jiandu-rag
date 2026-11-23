"""
批量写入/更新 daily_slips（每日一牍排期）。

CSV UTF-8，首行为表头，列名（不区分大小写）：
  feature_date — YYYY-MM-DD
  slip_code 或 slip_id — 关联 bamboo_slips
  quiz_question
  quiz_options — JSON 数组字符串，如 ["A","B","C","D"]；或用 | 分隔，如 A|B|C|D
  correct_index — 0 起
  fun_fact — 可选
  quizzes_json — 可选，JSON 字符串（多题扩展）

用法（backend 目录）:
  python scripts/import_daily_schedule_csv.py path/to/schedule.csv
  python scripts/import_daily_schedule_csv.py schedule.csv --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), override=True)

os.environ.setdefault("SKIP_STARTUP_CHROMA_SYNC", "1")

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import BambooSlip, DailySlip  # noqa: E402


def _norm_header(h: str) -> str:
    return (h or "").strip().lower().replace("\ufeff", "")


def _parse_options(raw: str) -> list:
    raw = (raw or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        v = json.loads(raw)
        if not isinstance(v, list):
            raise ValueError("quiz_options JSON 须为数组")
        return [str(x) for x in v]
    return [x.strip() for x in raw.split("|") if x.strip()]


def _resolve_slip(row: dict) -> BambooSlip | None:
    code = (row.get("slip_code") or "").strip()
    if code:
        return BambooSlip.query.filter_by(code=code).first()
    sid = row.get("slip_id")
    if sid is not None and str(sid).strip():
        try:
            return BambooSlip.query.get(int(sid))
        except (TypeError, ValueError):
            return None
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", type=str, help="排期 CSV 路径")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = args.csv_path
    if not os.path.isfile(path):
        print(f"文件不存在: {path}")
        sys.exit(1)

    app = create_app()
    inserted = updated = skipped = 0

    with app.app_context():
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                print("CSV 无表头")
                sys.exit(1)

            for i, raw_row in enumerate(reader, start=2):
                row = {_norm_header(k): (v or "").strip() for k, v in raw_row.items()}
                try:
                    fd = row.get("feature_date") or ""
                    d = date.fromisoformat(fd)
                except ValueError:
                    print(f"第 {i} 行：feature_date 无效 {row.get('feature_date')!r}，跳过")
                    skipped += 1
                    continue

                slip = _resolve_slip(row)
                if not slip:
                    print(f"第 {i} 行：找不到简牍 slip_code/slip_id，跳过")
                    skipped += 1
                    continue

                qq = row.get("quiz_question") or ""
                qo_raw = row.get("quiz_options") or ""
                try:
                    ci = int(row.get("correct_index", ""))
                except ValueError:
                    print(f"第 {i} 行：correct_index 无效，跳过")
                    skipped += 1
                    continue

                try:
                    qo = _parse_options(qo_raw)
                except json.JSONDecodeError as e:
                    print(f"第 {i} 行：quiz_options 解析失败 {e}，跳过")
                    skipped += 1
                    continue

                if not qq or len(qo) < 2:
                    print(f"第 {i} 行：题目或选项不足，跳过")
                    skipped += 1
                    continue
                if ci < 0 or ci >= len(qo):
                    print(f"第 {i} 行：correct_index 越界，跳过")
                    skipped += 1
                    continue

                fun_fact = row.get("fun_fact") or None
                if fun_fact == "":
                    fun_fact = None

                quizzes_json = None
                qj = row.get("quizzes_json")
                if qj:
                    try:
                        quizzes_json = json.loads(qj)
                    except json.JSONDecodeError:
                        print(f"第 {i} 行：quizzes_json 非法 JSON，跳过")
                        skipped += 1
                        continue

                existing = DailySlip.query.filter_by(feature_date=d).first()
                if args.dry_run:
                    print(
                        f"[dry-run] {d} slip={slip.code} quiz={qq[:40]}... opts={len(qo)} correct={ci}"
                    )
                    continue

                if existing:
                    existing.slip_id = slip.id
                    existing.quiz_question = qq[:512]
                    existing.quiz_options = qo
                    existing.correct_index = ci
                    existing.fun_fact = fun_fact
                    existing.quizzes_json = quizzes_json
                    updated += 1
                else:
                    db.session.add(
                        DailySlip(
                            slip_id=slip.id,
                            feature_date=d,
                            quiz_question=qq[:512],
                            quiz_options=qo,
                            correct_index=ci,
                            fun_fact=fun_fact,
                            quizzes_json=quizzes_json,
                        )
                    )
                    inserted += 1

        if not args.dry_run:
            db.session.commit()

    print(
        f"完成：新增 {inserted}，更新 {updated}，跳过 {skipped}；dry_run={args.dry_run}"
    )


if __name__ == "__main__":
    main()
