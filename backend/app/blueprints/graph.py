from flask import Blueprint, jsonify, request

from app.services import neo4j_service as neo

bp = Blueprint("graph", __name__)


@bp.get("/subgraph")
def subgraph():
    limit = request.args.get("limit", default=120, type=int) or 120
    no_site = str(request.args.get("no_site", "0")).lower() in ("1", "true", "yes")
    site = (request.args.get("site") or "").strip() or None
    tag = (request.args.get("tag") or "").strip() or None
    slip_code = (request.args.get("slip_code") or "").strip() or None
    slip_id = request.args.get("slip_id", type=int)
    data = neo.fetch_graph_subgraph(
        limit_nodes=limit,
        include_site_edges=not no_site,
        site=site,
        tag=tag,
        slip_code=slip_code,
        slip_id=slip_id,
    )
    return jsonify(data)


@bp.get("/seed-cypher")
def seed_cypher():
    return jsonify({"cypher": neo.seed_hint_cypher()})
