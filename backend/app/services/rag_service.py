"""问牍检索与作答：关键词与向量两路召回，RRF 融合，材料不足则改写或拒答。"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List, Optional

from flask import current_app
from sqlalchemy import or_, text

from app.constants import (
    RAG_HYDE,
    RAG_MAX_REWRITES,
    RAG_POOL,
    RAG_RRF_K,
    RAG_TOP_K,
    RAG_USE_CHROMA,
    RAG_USE_RERANK,
)
from app.extensions import db
from app.models import BambooSlip
from app.services import deepseek as ds
from app.services.rag_agent import heuristic_rewrite, iterate_plan
from app.services.rag_fusion import rrf_fuse
from app.services.rag_keywords import extract_keywords, trad_variants
from app.services.rag_rerank import rerank_docs

_chroma = None
_embedder = None

SYSTEM_PROMPT = (
    "你是「问牍·青声」的简牍讲读助手。只根据「材料」作答，不要编造材料里没有的人物、数量、地点或事件。"
    "材料没有写到的部分，直接说明材料未记载。"
    "引用时用方括号标出简牍编号，例如 [DJ-train-1]。文末用一行列出所据编号。"
)


def _chroma_collection():
    global _chroma
    if _chroma is not None:
        return _chroma
    import chromadb
    from chromadb.utils import embedding_functions

    persist = current_app.config.get("CHROMA_PERSIST_DIR", "./chroma_data")
    client = chromadb.PersistentClient(path=persist)
    model_name = (
        current_app.config.get("EMBEDDING_MODEL")
        or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
    _chroma = client.get_or_create_collection(name="bamboo_slips", embedding_function=ef)
    return _chroma


def sync_slips_to_chroma_if_possible() -> Dict[str, Any]:
    """将 MySQL 中简牍同步到 Chroma；大批量时分批 upsert 降低内存峰值。"""
    try:
        col = _chroma_collection()
        batch = int(current_app.config.get("CHROMA_UPSERT_BATCH") or 256)
        total = 0
        while True:
            slips: List[BambooSlip] = (
                BambooSlip.query.order_by(BambooSlip.id.asc()).offset(total).limit(batch).all()
            )
            if not slips:
                break
            ids = [str(s.id) for s in slips]
            docs = [
                f"{s.title}\n释文：{s.transcription}\n白话：{s.vernacular}\n遗址：{s.site_name or ''}"
                for s in slips
            ]
            metas = [{"code": s.code, "title": s.title} for s in slips]
            col.upsert(ids=ids, documents=docs, metadatas=metas)
            total += len(slips)
            if len(slips) < batch:
                break
        return {"ok": True, "count": total, "mode": "chroma", "batch": batch}
    except Exception as e:
        return {"ok": False, "error": str(e), "mode": "fallback"}


def _slip_row_ctx(s: BambooSlip) -> Dict[str, Any]:
    blob = f"{s.title}\n释文：{s.transcription}\n白话：{s.vernacular}"
    return {
        "id": s.id,
        "code": s.code,
        "title": s.title,
        "transcription": s.transcription or "",
        "vernacular": s.vernacular or "",
        "snippet": blob[:1200],
    }


def _keyword_forms(query: str) -> List[str]:
    forms: List[str] = []
    for kw in extract_keywords(query):
        for variant in trad_variants(kw):
            if variant not in forms:
                forms.append(variant)
    return forms[:16]


def _score_slip(row: BambooSlip, forms: List[str]) -> int:
    blob = f"{row.code}\n{row.title}\n{row.transcription or ''}\n{row.vernacular or ''}"
    score = 0
    for form in forms:
        if form == row.code:
            score += 50
        elif form in blob:
            score += 2 if len(form) >= 3 else 1
    return score


def _keyword_ranked(query: str, k: int) -> List[Dict[str, Any]]:
    forms = _keyword_forms(query)
    if not forms:
        return []

    found: Dict[int, BambooSlip] = {}
    for form in forms:
        rows = (
            BambooSlip.query.filter(
                or_(
                    BambooSlip.code == form,
                    BambooSlip.transcription.contains(form),
                    BambooSlip.vernacular.contains(form),
                    BambooSlip.title.contains(form),
                )
            )
            .limit(20)
            .all()
        )
        for row in rows:
            found[int(row.id)] = row
    use_ft = current_app.config.get("SLIPS_USE_FULLTEXT") and db.engine.dialect.name == "mysql"
    if use_ft:
        try:
            ft = text(
                "MATCH(bamboo_slips.title, bamboo_slips.transcription, bamboo_slips.vernacular) "
                "AGAINST (:kw IN NATURAL LANGUAGE MODE)"
            )
            for row in BambooSlip.query.filter(ft.bindparams(kw=" ".join(forms))).limit(20).all():
                found[int(row.id)] = row
        except Exception:
            pass
    ranked = [(_score_slip(row, forms), row) for row in found.values()]
    ranked = [item for item in ranked if item[0] > 0]
    ranked.sort(key=lambda item: (-item[0], item[1].id))

    def row_blob(row: BambooSlip) -> str:
        return f"{row.code}\n{row.title}\n{row.transcription or ''}\n{row.vernacular or ''}"

    chosen: List[BambooSlip] = []
    seen: set[int] = set()

    def add(row: BambooSlip) -> None:
        if int(row.id) in seen:
            return
        seen.add(int(row.id))
        chosen.append(row)

    for form in forms:
        if any(form == row.code or form in row_blob(row) for row in chosen):
            continue
        for _score, row in ranked:
            if form == row.code or form in row_blob(row):
                add(row)
                break
    for _score, row in ranked:
        if len(chosen) >= k:
            break
        add(row)
    chosen.sort(key=lambda row: (-_score_slip(row, forms), row.id))
    return [_slip_row_ctx(row) for row in chosen[:k]]


def _hyde_query_text(user_question: str) -> str:
    try:
        hy = ds.chat_completion(
            [
                {
                    "role": "system",
                    "content": "你是简牍检索助手。根据用户问题，写一段不超过200字、像出土简牍释文摘要一样的假想材料，"
                    "便于向量检索匹配真实简牍；不要输出问答格式。",
                },
                {"role": "user", "content": user_question[:1500]},
            ],
            temperature=0.4,
            timeout=25,
        )
        t = (hy or "").strip()
        return t[:800] if t else user_question
    except Exception:
        return user_question


def _embed_texts(texts: List[str]) -> List[List[float]]:
    """用本地缓存的嵌入模型编码。不走 Chroma 自带的在线加载。"""
    global _embedder
    if _embedder is None:
        import os

        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer

        model_name = (
            current_app.config.get("EMBEDDING_MODEL")
            or "BAAI/bge-m3"
        )
        _embedder = SentenceTransformer(model_name, device="cpu")
    vectors = _embedder.encode(list(texts), normalize_embeddings=False)
    return [vector.tolist() for vector in vectors]


def _vector_collection():
    import chromadb

    persist = current_app.config.get("CHROMA_PERSIST_DIR", "./chroma_data")
    client = chromadb.PersistentClient(path=persist)
    return client.get_collection(name="bamboo_slips")


def _vector_ranked(query: str, k: int) -> List[Dict[str, Any]]:
    qtext = _hyde_query_text(query) if RAG_HYDE and query.strip() else query
    _vector_ranked.last_error = None
    try:
        col = _vector_collection()
        res = col.query(query_embeddings=_embed_texts([qtext]), n_results=k, include=["metadatas", "documents"])
    except Exception as exc:
        _vector_ranked.last_error = exc
        return []
    out: List[Dict[str, Any]] = []
    ids = (res.get("ids") or [[]])[0] if res else []
    docs = (res.get("documents") or [[]])[0] if res else []
    metas = (res.get("metadatas") or [[]])[0] if res else []
    for i, sid in enumerate(ids or []):
        try:
            slip_id = int(sid)
        except (TypeError, ValueError):
            continue
        meta = metas[i] if i < len(metas) and metas[i] else {}
        doc = docs[i] if i < len(docs) and docs[i] else ""
        out.append(
            {
                "id": slip_id,
                "code": meta.get("code"),
                "title": meta.get("title"),
                "snippet": (doc or "")[:800],
            }
        )
    return out


def _hydrate(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not items:
        return []
    ids = [int(item["id"]) for item in items]
    rows = BambooSlip.query.filter(BambooSlip.id.in_(ids)).all()
    by_id = {int(row.id): row for row in rows}
    out: List[Dict[str, Any]] = []
    for item in items:
        row = by_id.get(int(item["id"]))
        merged = _slip_row_ctx(row) if row else dict(item)
        merged["rrf_score"] = item.get("rrf_score")
        merged["sources"] = item.get("sources") or []
        out.append(merged)
    return out


def rank_retrieval(query: str, mode: str, *, pool: int = 20, top_k: int = 5) -> List[Dict[str, Any]]:
    """按指定通路排序。mode 为 keyword、vector、rrf、rrf_rerank、keyword_rerank。"""
    width = max(top_k, pool)
    keyword_docs = [] if mode == "vector" else _keyword_ranked(query, width)
    vector_docs = [] if mode in ("keyword", "keyword_rerank") else _vector_ranked(query, width)
    if mode == "keyword":
        return keyword_docs[:top_k]
    if mode == "vector":
        return _hydrate(vector_docs[:top_k])
    if mode == "keyword_rerank":
        return rerank_docs(query, keyword_docs[:width], top_k)
    lists = []
    if keyword_docs:
        lists.append(("keyword", keyword_docs))
    if vector_docs:
        lists.append(("vector", vector_docs))
    if not lists:
        return []
    fused = _hydrate(rrf_fuse(lists, rrf_k=RAG_RRF_K, top_n=width))
    if mode == "rrf_rerank":
        return rerank_docs(query, fused, top_k)
    return fused[:top_k]


def retrieve_hybrid(query: str, k: int | None = None) -> List[Dict[str, Any]]:
    """关键词与向量分别召回，RRF 融合后再按配置重排。某一路没开时只用剩下的那一路。"""
    kk = k if k is not None else RAG_TOP_K
    pool = max(kk, RAG_POOL)
    if RAG_USE_CHROMA and RAG_USE_RERANK:
        mode = "rrf_rerank"
    elif RAG_USE_CHROMA:
        mode = "rrf"
    elif RAG_USE_RERANK:
        mode = "keyword_rerank"
    else:
        mode = "keyword"
    return rank_retrieval(query, mode, pool=pool, top_k=kk)


def retrieve_context(query: str, k: int | None = None) -> List[Dict[str, Any]]:
    """兼容旧调用：返回融合后的前 k 条。"""
    return retrieve_hybrid(query, k)


def _load_focus(slip_id: Optional[int]) -> Optional[Dict[str, Any]]:
    if slip_id is None:
        return None
    row = db.session.get(BambooSlip, slip_id)
    if not row:
        return None
    doc = _slip_row_ctx(row)
    doc["sources"] = [{"path": "focus", "rank": 0}]
    return doc


def _llm_rewrite(question: str) -> Optional[str]:
    key = current_app.config.get("DEEPSEEK_API_KEY") or ""
    if not key:
        return None
    try:
        text_out = ds.chat_completion(
            [
                {
                    "role": "system",
                    "content": "把用户问题改写成一行简牍检索关键词，用空格分隔，不要回答问题，不要解释。",
                },
                {"role": "user", "content": question[:500]},
            ],
            temperature=0.1,
            timeout=25,
        )
    except Exception:
        return None
    line = (text_out or "").strip().splitlines()[0].strip().strip("「」\"'") if text_out else ""
    if not line or line.startswith("（未配置") or len(line) > 80:
        return None
    return line


def _rewrite(question: str, keywords: List[str], attempt: int, keyword_hits: int = 0) -> str:
    if attempt == 1 and keyword_hits > 0:
        rewritten = _llm_rewrite(question)
        if rewritten:
            return rewritten
    return heuristic_rewrite(question, keywords, attempt)


def _context_text(docs: List[Dict[str, Any]]) -> str:
    parts = []
    for doc in docs:
        body = (doc.get("transcription") or doc.get("snippet") or "")[:1200]
        vern = (doc.get("vernacular") or "")[:600]
        parts.append(f"[{doc.get('code') or doc.get('id')}] {doc.get('title')}\n释文：{body}\n白话：{vern}")
    return "\n\n".join(parts)


def _messages(question: str, docs: List[Dict[str, Any]]) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"材料：\n{_context_text(docs)}\n\n问题：{question}"},
    ]


def via_label(sources: List[Dict[str, Any]] | None) -> str:
    paths = {str(item.get("path")) for item in (sources or []) if item.get("path")}
    retrieval = ""
    if "keyword" in paths and "vector" in paths:
        retrieval = "关键词+向量"
    elif "vector" in paths:
        retrieval = "向量"
    elif "keyword" in paths:
        retrieval = "关键词"
    if "rerank" in paths and retrieval:
        retrieval = retrieval + " · 重排"
    if "focus" in paths:
        return "当前简牍" + (f" · {retrieval}" if retrieval else "")
    return retrieval


def public_references(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    refs = []
    for doc in docs:
        refs.append(
            {
                "id": doc.get("id"),
                "code": doc.get("code"),
                "title": doc.get("title"),
                "transcription": (doc.get("transcription") or "")[:2000],
                "vernacular": (doc.get("vernacular") or "")[:800],
                "snippet": (doc.get("snippet") or "")[:400],
                "via": via_label(doc.get("sources")),
            }
        )
    return refs


def _done_event(plan: Dict[str, Any]) -> Dict[str, Any]:
    docs = [] if plan.get("refused") else plan.get("docs") or []
    return {
        "type": "done",
        "route": plan.get("route"),
        "refused": bool(plan.get("refused")),
        "references": public_references(docs),
        "attempts": plan.get("attempts") or [],
    }


def iter_rag_events(question: str, slip_id: Optional[int] = None, *, llm_rewrite: bool = True) -> Iterator[Dict[str, Any]]:
    focus = _load_focus(slip_id)

    def retrieve(query: str) -> List[Dict[str, Any]]:
        return retrieve_hybrid(query, RAG_TOP_K)

    def rewrite(question_text: str, keywords: List[str], attempt: int, keyword_hits: int = 0) -> str:
        if llm_rewrite:
            return _rewrite(question_text, keywords, attempt, keyword_hits)
        return heuristic_rewrite(question_text, keywords, attempt)

    plan: Dict[str, Any] | None = None
    for event in iterate_plan(
        question,
        retrieve,
        rewrite=rewrite,
        slip=focus,
        slip_id=slip_id,
        max_rewrites=RAG_MAX_REWRITES,
        top_k=RAG_TOP_K,
    ):
        if event.get("type") == "ready":
            plan = event["plan"]
            break
        if event.get("type") == "done":
            yield _done_event(event["plan"])
            return
        yield event

    if plan is None:
        return
    yield {"type": "status", "stage": "answer", "message": "正在根据材料绎读"}
    try:
        for piece in ds.chat_completion_stream(_messages(question, plan["docs"]), temperature=0.3):
            if piece:
                yield {"type": "token", "text": piece}
    except Exception:
        yield {"type": "token", "text": "（牍师暂时无法生成绎读，请稍后再试。）"}
    yield _done_event(plan)


def plan_question(question: str, slip_id: Optional[int] = None, *, llm_rewrite: bool = False) -> Dict[str, Any]:
    """只跑检索与判断，不调用生成模型。评测用。"""
    focus = _load_focus(slip_id)

    def retrieve(query: str) -> List[Dict[str, Any]]:
        return retrieve_hybrid(query, RAG_TOP_K)

    def rewrite(question_text: str, keywords: List[str], attempt: int, keyword_hits: int = 0) -> str:
        if llm_rewrite:
            return _rewrite(question_text, keywords, attempt, keyword_hits)
        return heuristic_rewrite(question_text, keywords, attempt)

    for event in iterate_plan(
        question,
        retrieve,
        rewrite=rewrite,
        slip=focus,
        slip_id=slip_id,
        max_rewrites=RAG_MAX_REWRITES,
        top_k=RAG_TOP_K,
    ):
        if event.get("type") in ("ready", "done"):
            return event["plan"]
    return {
        "route": "retrieve",
        "refused": True,
        "docs": [],
        "attempts": [],
        "direct_answer": None,
    }


def answer_with_rag(question: str, slip_id: Optional[int] = None) -> Dict[str, Any]:
    steps: List[Dict[str, str]] = []
    parts: List[str] = []
    done: Dict[str, Any] = {}
    for event in iter_rag_events(question, slip_id=slip_id, llm_rewrite=True):
        if event.get("type") == "status":
            steps.append({"stage": event.get("stage") or "", "message": event.get("message") or ""})
        elif event.get("type") == "token":
            parts.append(event.get("text") or "")
        elif event.get("type") == "done":
            done = event
    return {
        "answer": "".join(parts),
        "references": done.get("references") or [],
        "refused": bool(done.get("refused")),
        "route": done.get("route") or "retrieve",
        "rag_meta": {
            "top_k": RAG_TOP_K,
            "hyde": bool(RAG_HYDE),
            "chroma": bool(RAG_USE_CHROMA),
            "rerank": bool(RAG_USE_RERANK),
            "pool": RAG_POOL,
            "slip_focus": slip_id is not None,
            "fusion": "rrf",
            "steps": steps,
            "attempts": done.get("attempts") or [],
            "refused": bool(done.get("refused")),
            "route": done.get("route") or "retrieve",
        },
    }


def stream_answer_with_rag(question: str, slip_id: Optional[int] = None) -> Iterator[str]:
    """SSE：每条事件一行 data JSON。"""
    for event in iter_rag_events(question, slip_id=slip_id, llm_rewrite=True):
        yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
