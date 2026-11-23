from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.extensions import db, limiter
from app.models import AnalyticsEvent

bp = Blueprint("analytics", __name__)


@bp.post("/event")
@limiter.limit("90 per minute")
def track_event():
    data = request.get_json(silent=True) or {}
    event_type = (data.get("event_type") or "").strip()[:64]
    if not event_type:
        return jsonify({"error": "event_type 必填"}), 400
    uid = None
    try:
        verify_jwt_in_request(optional=True)
        raw = get_jwt_identity()
        if raw:
            uid = int(raw)
    except Exception:
        pass
    path = (data.get("path") or "")[:512]
    meta = data.get("meta")
    if meta is not None and not isinstance(meta, (dict, list)):
        meta = {"raw": str(meta)[:200]}
    row = AnalyticsEvent(event_type=event_type, user_id=uid, path=path, meta=meta)
    db.session.add(row)
    db.session.commit()
    return jsonify({"ok": True})
