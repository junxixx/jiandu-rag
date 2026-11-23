"""图结构增强推荐：Neo4j 中共标签/共遗址的简牍（说明书 TransE 的工程化替代）。"""
from __future__ import annotations

from typing import Any, Dict, List

from app.utils.home_slip_card import slip_home_card_dict

from app.services import neo4j_service as neo


def related_slip_ids_from_neo4j(slip_id: int, limit: int = 8) -> List[int]:
    """返回与给定 MySQL slip_id 在图中通过 Tag 共现相连的其它简牍 id。"""
    driver = None
    try:
        driver = neo._open_neo4j_driver()
        with driver.session() as session:
            rows = session.run(
                """
                MATCH (s:Slip {slip_id: $sid})-[:HAS_TAG]->(t:Tag)<-[:HAS_TAG]-(o:Slip)
                WHERE o <> s AND o.slip_id IS NOT NULL
                RETURN DISTINCT o.slip_id AS sid
                LIMIT $lim
                """,
                sid=int(slip_id),
                lim=int(limit),
            ).data()
        return [int(r["sid"]) for r in rows if r.get("sid") is not None]
    except Exception:
        return []
    finally:
        if driver is not None:
            driver.close()


def pack_slips_by_ids(ids: List[int]) -> List[Dict[str, Any]]:
    from app.models import BambooSlip

    if not ids:
        return []
    rows = BambooSlip.query.filter(BambooSlip.id.in_(ids)).all()
    m = {r.id: r for r in rows}
    return [
        slip_home_card_dict(m[i], read_count=None, catalog_fill=False)
        for i in ids
        if i in m
    ]
