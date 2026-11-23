"""问牍检索与拒答评测。不调用生成模型，也不写入虚构的 RAGAS 分数。"""

from __future__ import annotations

import json
import time
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
load_dotenv(BACKEND / ".env")

import sys

sys.path.insert(0, str(BACKEND))

from app import create_app
from app.services.rag_service import plan_question


def _blob(docs: list[dict], n: int = 3) -> str:
    parts: list[str] = []
    for doc in docs[:n]:
        for key in ("code", "title", "transcription", "vernacular", "snippet"):
            val = doc.get(key)
            if val:
                parts.append(str(val))
    return "\n".join(parts)


def _judge(item: dict, plan: dict) -> tuple[bool, str]:
    kind = item["kind"]
    if kind == "in_corpus":
        hit = (not plan.get("refused")) and item["expect_text"] in _blob(plan.get("docs") or [])
        return hit, "recall@3"
    if kind == "out_of_corpus":
        return bool(plan.get("refused")), "refuse"
    if kind == "chat":
        return plan.get("route") == "chat" and not plan.get("refused"), "chat"
    return False, "unknown"


def main() -> None:
    dataset = json.loads((HERE / "eval_dataset.json").read_text(encoding="utf-8"))
    app = create_app()
    rows = []
    with app.app_context():
        for item in dataset:
            started = time.perf_counter()
            plan = plan_question(item["question"], llm_rewrite=False)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            ok, metric = _judge(item, plan)
            docs = plan.get("docs") or []
            rows.append(
                {
                    "id": item["id"],
                    "kind": item["kind"],
                    "question": item["question"],
                    "metric": metric,
                    "ok": ok,
                    "refused": bool(plan.get("refused")),
                    "route": plan.get("route"),
                    "elapsed_ms": elapsed_ms,
                    "top_codes": [d.get("code") for d in docs[:3]],
                }
            )
            mark = "ok" if ok else "MISS"
            print(f"{mark}\t{item['id']}\t{elapsed_ms}ms\t{plan.get('route')}\trefused={plan.get('refused')}\t{rows[-1]['top_codes']}")

    def rate(kind: str) -> dict:
        group = [row for row in rows if row["kind"] == kind]
        hit = sum(1 for row in group if row["ok"])
        return {"n": len(group), "hit": hit, "rate": round(hit / len(group), 4) if group else None}

    summary = {
        "n": len(rows),
        "in_corpus_recall_at_3": rate("in_corpus"),
        "out_of_corpus_refuse": rate("out_of_corpus"),
        "chat_routed": rate("chat"),
        "mean_elapsed_ms": round(sum(row["elapsed_ms"] for row in rows) / len(rows), 1) if rows else None,
        "note": "只评检索、拒答和闲聊分流，不含生成忠实度，也不是 RAGAS 分数。",
    }
    payload = {"summary": summary, "items": rows}
    (HERE / "latest_results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
