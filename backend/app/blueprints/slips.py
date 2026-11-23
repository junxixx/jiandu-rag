from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import or_, text

from app.extensions import db
from app.models import BambooSlip
from app.services import slip_suggest_service as slip_suggest

bp = Blueprint("slips", __name__)


def _slip_search_query(kw: str):
    """有关键词时的过滤条件；MySQL + FULLTEXT 索引 + SLIPS_USE_FULLTEXT 时走 MATCH，否则 LIKE。"""
    if not kw:
        return BambooSlip.query
    like = f"%{kw}%"
    use_ft = current_app.config.get("SLIPS_USE_FULLTEXT") and db.engine.dialect.name == "mysql"
    if use_ft:
        try:
            ft = text(
                "MATCH(bamboo_slips.title, bamboo_slips.transcription, bamboo_slips.vernacular) "
                "AGAINST (:kw IN NATURAL LANGUAGE MODE)"
            )
            return BambooSlip.query.filter(
                or_(ft.bindparams(kw=kw), BambooSlip.code.like(like))
            )
        except Exception:
            pass
    return BambooSlip.query.filter(
        or_(
            BambooSlip.title.like(like),
            BambooSlip.code.like(like),
            BambooSlip.transcription.like(like),
            BambooSlip.vernacular.like(like),
        )
    )


def _slip_item(r: BambooSlip):
    return {
        "id": r.id,
        "code": r.code,
        "title": r.title,
        "site_name": r.site_name,
        "era": r.era,
        "image_url": r.image_url,
    }


@bp.get("")
def list_slips():
    size = min(max(int(request.args.get("size", 24)), 1), 60)
    kw = (request.args.get("q") or "").strip()
    raw_after = (request.args.get("after_id") or "").strip()
    if raw_after.isdigit():
        after_id = int(raw_after)
        q = _slip_search_query(kw).filter(BambooSlip.id > after_id).order_by(BambooSlip.id.asc()).limit(size + 1)
        rows = q.all()
        has_more = len(rows) > size
        rows = rows[:size]
        next_after = rows[-1].id if rows and has_more else None
        return jsonify(
            {
                "items": [_slip_item(r) for r in rows],
                "size": size,
                "has_more": has_more,
                "next_after_id": next_after,
                "total": None,
                "page": None,
            }
        )

    page = max(int(request.args.get("page", 1)), 1)
    q = _slip_search_query(kw)
    q = q.order_by(BambooSlip.id.asc())
    total = q.count()
    rows = q.offset((page - 1) * size).limit(size).all()
    return jsonify(
        {
            "total": total,
            "page": page,
            "size": size,
            "has_more": None,
            "next_after_id": None,
            "items": [_slip_item(r) for r in rows],
        }
    )


@bp.get("/<int:sid>/suggested-questions")
def suggested_questions(sid):
    """F1.4 猜你想问：基于当前简牍生成 3 条问牍提示。"""
    r = BambooSlip.query.get(sid)
    if not r:
        return jsonify({"error": "简牍不存在"}), 404
    items = slip_suggest.suggested_questions_for_slip(r)
    return jsonify({"slip_id": sid, "questions": items})


@bp.get("/<int:sid>")
def get_slip(sid):
    r = BambooSlip.query.get(sid)
    if not r:
        return jsonify({"error": "简牍不存在"}), 404
    return jsonify(
        {
            "id": r.id,
            "code": r.code,
            "title": r.title,
            "image_url": r.image_url,
            "transcription": r.transcription,
            "vernacular": r.vernacular,
            "site_name": r.site_name,
            "era": r.era,
            "tags": r.tags,
        }
    )
