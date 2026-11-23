"""问牍状态机：意图 → 检索 → 质量判断 → 改写重试或拒答。不依赖 Web 框架。"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterator, List, Optional

from app.services.rag_keywords import asks_about_open_slip, extract_keywords, is_chitchat, keyword_hit

CHITCHAT_ANSWER = (
    "我是问牍·青声的牍师，只依据牍库里的简牍释文来回答。"
    "闲聊不必检索牍库。你可以直接问地名、官职、文书名或简牍编号，例如「居延的候长奉钱」。"
)
REFUSE_ANSWER = (
    "牍库材料不足以回答这一问题，我不能凭空编造。"
    "请换一个出现在简牍释文里的词再问，例如地名、官职、文书名或简牍编号。"
)

RetrieveFn = Callable[[str], List[Dict[str, Any]]]
RewriteFn = Callable[..., str]


def heuristic_rewrite(question: str, keywords: List[str], attempt: int, keyword_hits: int = 0) -> str:
    """不调用模型的改写：换成繁体形式，第二次只留最长的一个词。"""
    del question, keyword_hits
    forms: List[str] = []
    for kw in keywords:
        for variant in (kw,):
            if variant and variant not in forms:
                forms.append(variant)
        if len(kw) > 2 and kw[:2] not in forms:
            forms.append(kw[:2])
    from app.services.rag_keywords import trad_variants

    expanded: List[str] = []
    for form in forms:
        for variant in trad_variants(form):
            if variant not in expanded:
                expanded.append(variant)
    if attempt >= 2 and expanded:
        expanded = [max(expanded, key=len)]
    return " ".join(expanded[:8])


def _blob(docs: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for doc in docs:
        for key in ("code", "title", "transcription", "vernacular", "snippet"):
            val = doc.get(key)
            if val:
                parts.append(str(val))
    return "\n".join(parts)


def grade_context(
    question: str,
    docs: List[Dict[str, Any]],
    *,
    slip_id: Optional[int] = None,
) -> Dict[str, Any]:
    keywords = extract_keywords(question)
    if slip_id is not None and asks_about_open_slip(question):
        if any(int(d.get("id") or 0) == int(slip_id) for d in docs):
            return {"score": 1.0, "passed": True, "keyword_hits": len(keywords), "keywords": keywords}
    if not docs or not keywords:
        return {"score": 0.0, "passed": False, "keyword_hits": 0, "keywords": keywords}
    blob = _blob(docs)
    hits = sum(1 for kw in keywords if keyword_hit(kw, blob))
    n = len(keywords)
    ratio = hits / n
    if hits == 0:
        passed = False
    elif n == 1:
        passed = True
    else:
        passed = hits >= 2 and ratio >= 0.5
    return {"score": round(ratio, 4), "passed": passed, "keyword_hits": hits, "keywords": keywords}


def _merge(slip: Optional[Dict[str, Any]], docs: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set[int] = set()
    if slip:
        out.append(slip)
        seen.add(int(slip["id"]))
    for doc in docs:
        try:
            sid = int(doc.get("id"))
        except (TypeError, ValueError):
            continue
        if sid in seen:
            continue
        out.append(doc)
        seen.add(sid)
        if len(out) >= top_k:
            break
    return out[:top_k]


def _public_plan(
    *,
    route: str,
    refused: bool,
    docs: List[Dict[str, Any]],
    attempts: List[Dict[str, Any]],
    direct_answer: Optional[str],
) -> Dict[str, Any]:
    return {
        "route": route,
        "refused": refused,
        "docs": docs,
        "attempts": attempts,
        "direct_answer": direct_answer,
    }


def iterate_plan(
    question: str,
    retrieve: RetrieveFn,
    *,
    rewrite: Optional[RewriteFn] = None,
    slip: Optional[Dict[str, Any]] = None,
    slip_id: Optional[int] = None,
    max_rewrites: int = 2,
    top_k: int = 5,
) -> Iterator[Dict[str, Any]]:
    """产出 status/token/done/ready 事件。ready 表示材料足够，调用方再生成答案。"""
    rewrite_fn = rewrite or heuristic_rewrite
    q = (question or "").strip()
    yield {"type": "status", "stage": "route", "message": "正在分析意图"}

    if is_chitchat(q) and slip_id is None:
        plan = _public_plan(route="chat", refused=False, docs=[], attempts=[], direct_answer=CHITCHAT_ANSWER)
        yield {"type": "status", "stage": "chat", "message": "这是闲聊，不检索牍库"}
        yield {"type": "token", "text": CHITCHAT_ANSWER}
        yield {"type": "done", "plan": plan}
        return

    yield {"type": "status", "stage": "retrieve", "message": "正在检索简牍"}
    query = q
    seen_queries = {query}
    attempts: List[Dict[str, Any]] = []
    docs: List[Dict[str, Any]] = []
    refused = True
    rewrites = max(0, int(max_rewrites))

    for i in range(rewrites + 1):
        docs = _merge(slip, retrieve(query) or [], top_k)
        graded = grade_context(q, docs, slip_id=slip_id)
        attempts.append(
            {
                "query": query,
                "score": graded["score"],
                "passed": graded["passed"],
                "keyword_hits": graded["keyword_hits"],
                "keywords": graded["keywords"],
                "n_docs": len(docs),
            }
        )
        if graded["passed"] and docs:
            refused = False
            break
        if i >= rewrites:
            break
        yield {
            "type": "status",
            "stage": "rewrite",
            "message": f"材料不足，正在改写查询（第{i + 1}次）",
            "attempt": i + 1,
        }
        new_q = (rewrite_fn(q, graded["keywords"], i + 1, graded["keyword_hits"]) or "").strip()
        if not new_q or new_q in seen_queries:
            break
        seen_queries.add(new_q)
        query = new_q
        yield {"type": "status", "stage": "retrieve", "message": "正在按改写后的问法再检索"}

    if refused:
        plan = _public_plan(route="retrieve", refused=True, docs=[], attempts=attempts, direct_answer=REFUSE_ANSWER)
        yield {"type": "status", "stage": "refuse", "message": "材料仍不足，改为拒答"}
        yield {"type": "token", "text": REFUSE_ANSWER}
        yield {"type": "done", "plan": plan}
        return

    plan = _public_plan(route="retrieve", refused=False, docs=docs, attempts=attempts, direct_answer=None)
    yield {"type": "ready", "plan": plan}
