from flask import Blueprint, jsonify

from app.models import Topic

bp = Blueprint("topics", __name__)


@bp.get("")
def list_topics():
    rows = Topic.query.order_by(Topic.hot.desc(), Topic.id.asc()).limit(50).all()
    return jsonify(
        {
            "items": [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "post_count": t.post_count,
                    "hot": t.hot,
                }
                for t in rows
            ]
        }
    )
