"""倒数排名融合（RRF）。各路召回各自排序，按 1/(k+rank) 相加。"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple


def rrf_fuse(
    ranked_lists: Sequence[Tuple[str, Sequence[Dict[str, Any]]]],
    *,
    rrf_k: int = 60,
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """`ranked_lists` 为 (通路名, 按相关度从高到低的文档)。只保留带整数 id 的条目。"""
    scores: Dict[int, float] = {}
    payload: Dict[int, Dict[str, Any]] = {}
    sources: Dict[int, List[Dict[str, Any]]] = {}
    k = max(1, int(rrf_k))
    for name, docs in ranked_lists:
        for rank, doc in enumerate(docs, start=1):
            try:
                sid = int(doc.get("id"))
            except (TypeError, ValueError):
                continue
            scores[sid] = scores.get(sid, 0.0) + 1.0 / (k + rank)
            if sid not in payload:
                payload[sid] = dict(doc)
            sources.setdefault(sid, []).append({"path": name, "rank": rank})
    ordered = sorted(scores, key=lambda i: (-scores[i], i))
    out: List[Dict[str, Any]] = []
    for sid in ordered[: max(1, int(top_n))]:
        row = dict(payload[sid])
        row["id"] = sid
        row["rrf_score"] = round(scores[sid], 6)
        row["sources"] = sources[sid]
        out.append(row)
    return out
