from flask import Blueprint, Response, jsonify, request, stream_with_context

from app.blueprints.admin import admin_required
from app.extensions import limiter
from app.services.rag_service import (
    answer_with_rag,
    stream_answer_with_rag,
    sync_slips_to_chroma_if_possible,
)

bp = Blueprint("rag", __name__)


def _parse_slip_id(raw) -> int | None:
    if raw is None:
        return None
    try:
        n = int(raw)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


@bp.post("/query")
@limiter.limit("30 per minute")
def query():
    data = request.get_json(silent=True) or {}
    q = (data.get("question") or "").strip()
    if not q:
        return jsonify({"error": "question 不能为空"}), 400
    slip_id = _parse_slip_id(data.get("slip_id"))
    result = answer_with_rag(q, slip_id=slip_id)
    return jsonify(result)


@bp.post("/query/stream")
@limiter.limit("20 per minute")
def query_stream():
    """流式输出绎读正文（UTF-8 纯文本分块），便于首字早显。"""
    data = request.get_json(silent=True) or {}
    q = (data.get("question") or "").strip()
    if not q:
        return jsonify({"error": "question 不能为空"}), 400
    slip_id = _parse_slip_id(data.get("slip_id"))

    def gen():
        for piece in stream_answer_with_rag(q, slip_id=slip_id):
            yield piece

    return Response(
        stream_with_context(gen()),
        mimetype="text/event-stream; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.post("/reindex")
@admin_required
@limiter.limit("6 per minute")
def reindex():
    """同步 MySQL → Chroma；须请求头 X-Admin-Token 与 .env ADMIN_TOKEN 一致。"""
    r = sync_slips_to_chroma_if_possible()
    return jsonify(r)
