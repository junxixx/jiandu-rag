"""
上线编排：按顺序执行牍库 → 向量索引 → Neo4j → 每日排期 → 任务徽章 → 雅集种子 → 抽检清单。

在 backend 目录执行（已配置 .env）:
  python scripts/go_live_pipeline.py --steps 1-7
  python scripts/go_live_pipeline.py --steps 2-4
  python scripts/go_live_pipeline.py --steps 1 --import-extra "--limit 100"
  python scripts/go_live_pipeline.py --steps 4 --daily-csv ../data/daily.csv

步骤说明：
  1  真牍入库 + 影像（子进程调用 import_deepjiandu.py，可用 --import-extra 传参）
  2  Chroma 全量 reindex（本进程 app 上下文）
  3  Neo4j 全量同步
  4  每日一牍：--daily-csv 导入 CSV；否则仅提示用 bootstrap_module_content / 管理端
  5  任务模板 + 徽章种子 + 打印积分常量
  6  雅集话题 + 演示帖（bootstrap_module_content --forum-only）
  7  打印 LLM prompt 抽检清单（见 scripts/prompt_audit.py）
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_BACKEND, ".env"), override=True)

os.environ.setdefault("SKIP_STARTUP_CHROMA_SYNC", "1")


def _parse_steps(spec: str) -> set[int]:
    spec = spec.strip()
    if "-" in spec:
        a, b = spec.split("-", 1)
        lo, hi = int(a), int(b)
        return set(range(lo, hi + 1))
    return {int(x.strip()) for x in spec.split(",") if x.strip()}


def _run_import(extra: list[str]) -> None:
    script = os.path.join(_BACKEND, "scripts", "import_deepjiandu.py")
    cmd = [sys.executable, script] + extra
    print("执行:", " ".join(cmd))
    r = subprocess.run(cmd, cwd=_BACKEND)
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def _step2_chroma() -> None:
    from app import create_app  # noqa: E402
    from app.services.rag_service import sync_slips_to_chroma_if_possible  # noqa: E402

    app = create_app()
    with app.app_context():
        r = sync_slips_to_chroma_if_possible()
        print("Chroma:", r)


def _step3_neo4j() -> None:
    from app import create_app  # noqa: E402
    from app.services import neo4j_service as neo  # noqa: E402

    app = create_app()
    with app.app_context():
        r = neo.sync_bamboo_slips_full_from_mysql()
        print("Neo4j:", r)
        if not r.get("ok"):
            raise SystemExit(1)


def _step4_daily(csv_path: str | None) -> None:
    if csv_path:
        script = os.path.join(_BACKEND, "scripts", "import_daily_schedule_csv.py")
        cmd = [sys.executable, script, csv_path]
        print("执行:", " ".join(cmd))
        r = subprocess.run(cmd, cwd=_BACKEND)
        if r.returncode != 0:
            raise SystemExit(r.returncode)
    else:
        print(
            "步骤 4：未传 --daily-csv。可任选其一：\n"
            "  python scripts/import_daily_schedule_csv.py <排期.csv>\n"
            "  python scripts/bootstrap_module_content.py --daily-only\n"
            "  或管理端 POST /api/admin/daily（X-Admin-Token）"
        )


def _step5_rewards() -> None:
    for name in ("seed_quest_templates.py", "seed_badges_only.py", "print_rewards_config.py"):
        script = os.path.join(_BACKEND, "scripts", name)
        r = subprocess.run([sys.executable, script], cwd=_BACKEND)
        if r.returncode != 0:
            raise SystemExit(r.returncode)


def _step6_forum() -> None:
    script = os.path.join(_BACKEND, "scripts", "seed_topics.py")
    r = subprocess.run([sys.executable, script], cwd=_BACKEND)
    if r.returncode != 0:
        raise SystemExit(r.returncode)
    script = os.path.join(_BACKEND, "scripts", "bootstrap_module_content.py")
    r = subprocess.run([sys.executable, script, "--forum-only"], cwd=_BACKEND)
    if r.returncode != 0:
        raise SystemExit(r.returncode)
    print(
        "步骤 6：审帖请用 GET/PATCH /api/admin/posts/pending 与 /api/admin/posts/<id>/moderate；"
        "敏感词 PUT /api/admin/kv/blocked_words"
    )


def _step7_prompts() -> None:
    script = os.path.join(_BACKEND, "scripts", "prompt_audit.py")
    r = subprocess.run([sys.executable, script], cwd=_BACKEND)
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", default="1-7", help="如 1-7 或 2,3,5")
    ap.add_argument(
        "--import-extra",
        default="",
        help="传给 import_deepjiandu.py 的额外参数（引号包裹），如 '--limit 500 --reindex'",
    )
    ap.add_argument("--daily-csv", default="", help="步骤 4：排期 CSV 路径")
    args = ap.parse_args()

    try:
        want = _parse_steps(args.steps)
    except ValueError:
        print("无效 --steps")
        sys.exit(2)

    for s in sorted(want):
        print(f"\n========== 步骤 {s} ==========")
        if s == 1:
            extra = args.import_extra.split() if args.import_extra.strip() else []
            _run_import(extra)
        elif s == 2:
            _step2_chroma()
        elif s == 3:
            _step3_neo4j()
        elif s == 4:
            _step4_daily(args.daily_csv.strip() or None)
        elif s == 5:
            _step5_rewards()
        elif s == 6:
            _step6_forum()
        elif s == 7:
            _step7_prompts()
        else:
            print(f"未知步骤 {s}，跳过")

    print("\n全部选定步骤已执行完毕。")


if __name__ == "__main__":
    main()
