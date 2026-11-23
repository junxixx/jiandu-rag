"""检索排序指标。只看标准简号是否出现在前 k 条里。"""

from __future__ import annotations

from typing import Iterable, Sequence


def first_relevant_rank(ranked_codes: Sequence[str], gold_codes: Iterable[str]) -> int | None:
    gold = {code for code in gold_codes if code}
    if not gold:
        return None
    for index, code in enumerate(ranked_codes, start=1):
        if code in gold:
            return index
    return None


def hit_at_k(rank: int | None, k: int = 5) -> bool:
    return rank is not None and rank <= k


def reciprocal_rank(rank: int | None, k: int = 5) -> float:
    if rank is None or rank > k:
        return 0.0
    return 1.0 / rank
