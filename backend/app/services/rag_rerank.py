"""用交叉编码器对已经召回的简牍重新排序。"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Sequence

_model = None


def rerank_model_name() -> str:
    return os.getenv("RAG_RERANK_MODEL", "BAAI/bge-reranker-base")


def _cross_encoder():
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder

        _model = CrossEncoder(rerank_model_name(), device="cpu")
    return _model


def order_by_scores(
    docs: Sequence[Dict[str, Any]],
    scores: Sequence[float],
    top_n: int,
) -> List[Dict[str, Any]]:
    paired = sorted(zip(scores, docs), key=lambda item: (-float(item[0]), str(item[1].get("code") or "")))
    out: List[Dict[str, Any]] = []
    for rank, (score, doc) in enumerate(paired[: max(1, int(top_n))], start=1):
        row = dict(doc)
        row["rerank_score"] = round(float(score), 4)
        sources = list(row.get("sources") or [])
        sources.append({"path": "rerank", "rank": rank})
        row["sources"] = sources
        out.append(row)
    return out


def _passage(doc: Dict[str, Any]) -> str:
    text = doc.get("transcription") or doc.get("snippet") or doc.get("title") or ""
    return str(text)[:256]


def rerank_docs(query: str, docs: Sequence[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
    """对候选简牍打分，取得分最高的 top_n 条。候选为空时原样返回。"""
    rows = [doc for doc in docs if doc]
    if not rows:
        return []
    pairs = [(query, _passage(doc)) for doc in rows]
    scores = _cross_encoder().predict(pairs, show_progress_bar=False)
    return order_by_scores(rows, [float(score) for score in scores], top_n)
