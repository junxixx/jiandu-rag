"""四列检索评测：只关键词、只向量、RRF、RRF 加重排。指标是 Hit@5 和 MRR@5，按标准简号计算。"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
load_dotenv(BACKEND / ".env")
sys.path.insert(0, str(BACKEND))

from app import create_app
from app.services.rag_metrics import first_relevant_rank, hit_at_k, reciprocal_rank
from app.services.rag_service import _vector_ranked, rank_retrieval

MODES = ("keyword", "vector", "rrf", "rrf_rerank")


def _summarize(rows: list[dict], mode: str) -> dict:
    hits = [row[mode]["hit"] for row in rows]
    rrs = [row[mode]["rr"] for row in rows]
    return {
        "n": len(rows),
        "hit_at_5": round(sum(hits) / len(hits), 4) if hits else None,
        "mrr_at_5": round(sum(rrs) / len(rrs), 4) if rrs else None,
    }


def main() -> None:
    dataset = json.loads((HERE / "eval_ranking.json").read_text(encoding="utf-8"))
    items = dataset["items"]
    if len(items) < 40:
        raise SystemExit(f"评测集只有 {len(items)} 题")
    app = create_app()
    rows = []
    with app.app_context():
        probe = _vector_ranked("居延", 1)
        if getattr(_vector_ranked, "last_error", None):
            raise SystemExit(f"向量检索不可用：{_vector_ranked.last_error}")
        if not probe:
            raise SystemExit("向量检索没有返回结果，不能把空结果当成四列分数")
        for item in items:
            started = time.perf_counter()
            scored = {}
            for mode in MODES:
                docs = rank_retrieval(item["question"], mode, pool=20, top_k=5)
                if mode in ("vector", "rrf", "rrf_rerank") and getattr(_vector_ranked, "last_error", None):
                    raise SystemExit(f"{item['id']} 向量检索失败：{_vector_ranked.last_error}")
                codes = [str(doc.get("code") or "") for doc in docs]
                rank = first_relevant_rank(codes, item["expect_codes"])
                scored[mode] = {
                    "hit": hit_at_k(rank, 5),
                    "rr": reciprocal_rank(rank, 5),
                    "rank": rank,
                    "top_codes": codes,
                }
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            rows.append(
                {
                    "id": item["id"],
                    "question": item["question"],
                    "expect_codes": item["expect_codes"],
                    "answer_span": item["answer_span"],
                    "elapsed_ms": elapsed_ms,
                    **scored,
                }
            )
            print(
                f"{item['id']}\t{elapsed_ms}ms\t"
                + "\t".join(f"{mode}={'Y' if scored[mode]['hit'] else 'n'}@{scored[mode]['rank']}" for mode in MODES)
            )

    summary = {mode: _summarize(rows, mode) for mode in MODES}
    summary["note"] = "Hit@5 / MRR@5 按 expect_codes 计算。没进前 5 的题倒数排名记 0。不是 RAGAS，也不是生成忠实度。"
    payload = {"summary": summary, "items": rows}
    (HERE / "ranking_results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
