import random
from datetime import date

from sqlalchemy import func

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models import BambooSlip, Topic, UserSlipProgress
from app.utils.home_slip_card import dj_subset_bucket, slip_home_card_dict

from app.chat_roles import character_cards_for_home
from app.services import graph_recommend_service as gre
from app.services import itemcf_service as icf

bp = Blueprint("recommend", __name__)


def _transcription_len_desc():
    """按释文字符长度排序（MySQL 用 CHAR_LENGTH，其余方言用 LENGTH）。"""
    if db.engine.dialect.name == "mysql":
        return func.char_length(BambooSlip.transcription).desc()
    return func.length(BambooSlip.transcription).desc()


def _pick_catalog_fill_slips(blocked: set[int], need: int, *, rng: random.Random) -> list[BambooSlip]:
    """A1+A2+A3：按日种子打散；train/val/test 均衡轮询；池内优先释文较长者。"""
    if need <= 0:
        return []
    q = BambooSlip.query
    if blocked:
        q = q.filter(~BambooSlip.id.in_(blocked))
    cap = min(max(need * 50, 600), 3000)
    pool = q.order_by(_transcription_len_desc()).limit(cap).all()
    if not pool:
        return []
    buckets: dict[str, list[BambooSlip]] = {"train": [], "val": [], "test": [], "other": []}
    for r in pool:
        buckets[dj_subset_bucket(r.code)].append(r)
    for k in buckets:
        buckets[k].sort(key=lambda x: (-len((x.transcription or "").strip()), rng.random()))
    order = ("train", "val", "test", "other")
    idxs = {k: 0 for k in order}
    picked: list[BambooSlip] = []
    seen = set(blocked)
    guard = 0
    while len(picked) < need and guard < need * 30:
        guard += 1
        progressed = False
        for k in order:
            if len(picked) >= need:
                break
            bi = buckets[k]
            while idxs[k] < len(bi):
                row = bi[idxs[k]]
                idxs[k] += 1
                if row.id in seen:
                    continue
                picked.append(row)
                seen.add(row.id)
                progressed = True
                break
        if not progressed:
            break
    if len(picked) < need:
        rest = [r for r in pool if r.id not in seen]
        rng.shuffle(rest)
        for r in rest:
            if len(picked) >= need:
                break
            picked.append(r)
            seen.add(r.id)
    return picked[:need]


def _pack_ordered(ids: list[int], counts: dict[int, int] | None = None) -> list[dict]:
    if not ids:
        return []
    rows = BambooSlip.query.filter(BambooSlip.id.in_(ids)).all()
    m = {r.id: r for r in rows}
    out: list[dict] = []
    for i in ids:
        if i not in m:
            continue
        rc = counts.get(i) if counts else None
        out.append(slip_home_card_dict(m[i], read_count=rc, catalog_fill=False))
    return out


@bp.get("/home")
@jwt_required(optional=True)
def home():
    """热门简牍 + 协同过滤 + ItemCF（Redis）+ 图增强 + 话题 + AI 角色（说明书 F1.3）。"""
    icf.maybe_warm_itemcf()

    # 首页热点/推荐展示条数：阅读数据不足时用牍库条目补齐，保证首页不显得“空”
    desired_hot = 18
    desired_for_you = 12
    daily_seed = int(date.today().strftime("%Y%m%d"))
    rng = random.Random(daily_seed)

    hot = (
        db.session.query(UserSlipProgress.slip_id, func.count(UserSlipProgress.id).label("cnt"))
        .group_by(UserSlipProgress.slip_id)
        .order_by(func.count(UserSlipProgress.id).desc())
        .limit(desired_hot)
        .all()
    )
    hot_ids = [h[0] for h in hot]
    hot_counts = {int(h[0]): int(h[1]) for h in hot}
    collab_ids: list[int] = []
    collab_counts: dict[int, int] = {}
    raw = get_jwt_identity()
    uid = int(raw) if raw else None
    mine: set[int] = set()

    if uid:
        mine = {r.slip_id for r in UserSlipProgress.query.filter_by(user_id=uid).limit(400).all()}
        q = (
            db.session.query(UserSlipProgress.slip_id, func.count(UserSlipProgress.id).label("cnt"))
            .filter(UserSlipProgress.user_id != uid)
        )
        if mine:
            q = q.filter(~UserSlipProgress.slip_id.in_(mine))
        others = (
            q.group_by(UserSlipProgress.slip_id)
            .order_by(func.count(UserSlipProgress.id).desc())
            .limit(desired_for_you)
            .all()
        )
        collab_ids = [o[0] for o in others]
        collab_counts = {int(o[0]): int(o[1]) for o in others}

    # 热点：优先用“大家读得多”的简牍；不足则按日种子 + 分层 + 释文长度补齐牍库
    hot_items = _pack_ordered(hot_ids, hot_counts) if hot_ids else []
    hot_used_catalog_fill = False
    if len(hot_items) < desired_hot:
        missing = desired_hot - len(hot_items)
        blocked = {int(x["id"]) for x in hot_items}
        fill_rows = _pick_catalog_fill_slips(blocked, missing, rng=rng)
        hot_items.extend(
            slip_home_card_dict(r, read_count=None, catalog_fill=True) for r in fill_rows
        )
        hot_used_catalog_fill = bool(fill_rows)

    for_you = (
        _pack_ordered(collab_ids, collab_counts)
        if collab_ids
        else list(hot_items[:desired_for_you])
    )

    itemcf_slips: list[dict] = []
    graph_slips: list[dict] = []
    if uid and mine:
        seed = next(iter(mine)) if mine else None
        if seed:
            icf_ids = [i for i in icf.similar_slip_ids(seed, 10) if i not in mine]
            itemcf_slips = _pack_ordered(icf_ids, None)
            g_ids = [i for i in gre.related_slip_ids_from_neo4j(seed, 8) if i not in mine]
            graph_slips = gre.pack_slips_by_ids(g_ids)

    topics = Topic.query.order_by(Topic.hot.desc(), Topic.id.asc()).limit(10).all()
    topic_items = [
        {"id": t.id, "name": t.name, "description": t.description, "hot": t.hot, "post_count": t.post_count}
        for t in topics
    ]

    return jsonify(
        {
            "hot": hot_items,
            "for_you": for_you,
            "topics": topic_items,
            "characters": character_cards_for_home(),
            "itemcf_slips": itemcf_slips,
            "graph_related_slips": graph_slips,
            "hot_used_catalog_fill": hot_used_catalog_fill,
            "daily_seed_ymd": daily_seed,
        }
    )


@bp.get("/graph-embedding-related")
@jwt_required(optional=True)
def graph_embedding_related():
    """
    说明书「TransE 图嵌入」轻量替代：以 Neo4j 共现一跳扩展作结构相似推荐。
    全量 TransE 训练成本高，本接口明确标注 method。
    """
    sid = request.args.get("slip_id", type=int)
    if not sid:
        return jsonify(
            {
                "method": "neo4j_cooccurrence",
                "note": "非 TransE 向量；由图谱一跳关联近似「图结构相似」",
                "slips": [],
            }
        )
    raw = get_jwt_identity()
    uid = int(raw) if raw else None
    mine = set()
    if uid:
        mine = {r.slip_id for r in UserSlipProgress.query.filter_by(user_id=uid).limit(400).all()}
    g_ids = [i for i in gre.related_slip_ids_from_neo4j(sid, 12) if i not in mine and i != sid]
    return jsonify(
        {
            "method": "neo4j_cooccurrence",
            "note": "说明书 TransE 的工程替代：Neo4j 子图扩展；可后续换真实图嵌入服务",
            "slips": gre.pack_slips_by_ids(g_ids),
        }
    )
