from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models import User
from app.services import story_service as ss

bp = Blueprint("story", __name__)


@bp.get("/progress")
@jwt_required()
def progress():
    uid = int(get_jwt_identity())
    return jsonify(ss.get_progress(uid))


@bp.post("/action")
@jwt_required()
def action():
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    target = (data.get("next_node_id") or "").strip()
    if not target:
        return jsonify({"error": "next_node_id 必填"}), 400
    r = ss.advance(uid, target)
    if not r.get("ok"):
        return jsonify(r), 400
    delta = int(r.get("points_delta") or 0)
    u = User.query.get(uid)
    if u and delta:
        u.points = (u.points or 0) + delta
        db.session.commit()
    return jsonify(r)
