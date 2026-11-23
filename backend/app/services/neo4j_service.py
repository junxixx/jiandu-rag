import re
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from app.models import BambooSlip
from app.extensions import db

from flask import current_app

from app.utils.slip_tags import parse_slip_tags

# 子图查询中允许的端点标签（含语料库类，非考古「遗址」）
_GRAPH_NODE_OR_A = (
    "(a:Slip OR a:Tag OR a:Person OR a:Site OR a:Event OR a:Corpus OR a:CorpusBatch)"
)
_GRAPH_NODE_OR_B = (
    "(b:Slip OR b:Tag OR b:Person OR b:Site OR b:Event OR b:Corpus OR b:CorpusBatch)"
)
_GRAPH_NODE_OR_O = (
    "(o:Slip OR o:Tag OR o:Person OR o:Site OR o:Event OR o:Corpus OR o:CorpusBatch)"
)

_DJ_SUBSET_RE = re.compile(r"^DJ-(train|val|test)-", re.IGNORECASE)


def _deepjiandu_corpus_info(code: str | None) -> Tuple[bool, str | None]:
    """是否为 DeepJiandu 导入 code（DJ- 前缀）；若是，返回 (True, train|val|test|None)。"""
    c = (code or "").strip()
    if not c.upper().startswith("DJ-"):
        return False, None
    m = _DJ_SUBSET_RE.match(c)
    if m:
        return True, m.group(1).lower()
    return True, None


def _open_neo4j_driver():
    """使用 basic_auth 显式传用户名密码，避免 neo4j-driver 6.x 下元组 auth 触发 missing credentials。"""
    from neo4j import GraphDatabase, basic_auth

    uri = (current_app.config.get("NEO4J_URI") or "").strip()
    user = (current_app.config.get("NEO4J_USER") or "neo4j").strip()
    password = (current_app.config.get("NEO4J_PASSWORD") or "").strip()
    if not uri:
        raise ValueError("NEO4J_URI 未配置")
    if not password:
        raise ValueError(
            "NEO4J_PASSWORD 为空。请在 backend/.env 填写与 Neo4j Desktop 创建数据库时一致的密码；"
            "等号后不要加英文引号（错误示例 NEO4J_PASSWORD=\"abc\" 可能把引号算进密码）。"
        )
    return GraphDatabase.driver(uri, auth=basic_auth(user, password))


def _ensure_schema(session) -> None:
    """尽力创建唯一约束（Neo4j 5+）；失败则忽略以兼容旧版。"""
    stmts = [
        "CREATE CONSTRAINT slip_code_unique IF NOT EXISTS FOR (s:Slip) REQUIRE s.code IS UNIQUE",
        "CREATE CONSTRAINT tag_name_unique IF NOT EXISTS FOR (t:Tag) REQUIRE t.name IS UNIQUE",
        "CREATE CONSTRAINT person_name_unique IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT site_name_unique IF NOT EXISTS FOR (x:Site) REQUIRE x.name IS UNIQUE",
        "CREATE CONSTRAINT event_name_unique IF NOT EXISTS FOR (e:Event) REQUIRE e.name IS UNIQUE",
        "CREATE CONSTRAINT corpus_name_unique IF NOT EXISTS FOR (c:Corpus) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT corpus_batch_key_unique IF NOT EXISTS FOR (b:CorpusBatch) REQUIRE b.key IS UNIQUE",
    ]
    for cypher in stmts:
        try:
            session.run(cypher)
        except Exception:
            pass


def _merge_slip_tx(tx, slip_id: int, code: str, title: str, site_name: str | None, tags: str | None) -> None:
    title_s = (title or "")[:512]
    tx.run(
        """
        MERGE (s:Slip {code: $code})
        SET s.slip_id = $slip_id, s.title = $title
        """,
        code=code,
        slip_id=slip_id,
        title=title_s,
    )
    site = (site_name or "").strip()
    if site:
        # 已有真实出土地时，去掉语料库挂靠，避免与考古语义混读
        tx.run(
            """
            MATCH (s:Slip {code: $code})
            OPTIONAL MATCH (s)-[rc:IN_CORPUS]->(:Corpus)
            DELETE rc
            OPTIONAL MATCH (s)-[rb:IN_DATA_BATCH]->(:CorpusBatch)
            DELETE rb
            """,
            code=code,
        )
        tx.run(
            """
            MATCH (s:Slip {code: $code})
            MERGE (x:Site {name: $site})
            MERGE (s)-[:EXCAVATED_AT]->(x)
            MERGE (s)-[:AT_SITE]->(x)
            """,
            code=code,
            site=site[:128],
        )
    else:
        tx.run(
            """
            MATCH (s:Slip {code: $code})
            OPTIONAL MATCH (s)-[r:EXCAVATED_AT|AT_SITE]->(:Site)
            DELETE r
            """,
            code=code,
        )
        is_dj, subset = _deepjiandu_corpus_info(code)
        if is_dj:
            corpus_name = "DeepJiandu（影像语料）"
            tx.run(
                """
                MATCH (s:Slip {code: $code})
                MERGE (root:Corpus {name: $corpus_name})
                ON CREATE SET root.kind = 'image_corpus',
                              root.note = '数据集节点，非考古出土地'
                MERGE (s)-[:IN_CORPUS]->(root)
                """,
                code=code,
                corpus_name=corpus_name,
            )
            if subset:
                bkey = f"dj:{subset}"
                blab = f"子集 · {subset}"
                tx.run(
                    """
                    MATCH (s:Slip {code: $code})
                    MATCH (root:Corpus {name: $corpus_name})
                    MERGE (b:CorpusBatch {key: $bkey})
                    ON CREATE SET b.label = $blab
                    MERGE (b)-[:PART_OF]->(root)
                    MERGE (s)-[:IN_DATA_BATCH]->(b)
                    """,
                    code=code,
                    corpus_name=corpus_name,
                    bkey=bkey,
                    blab=blab,
                )
            else:
                tx.run(
                    """
                    MATCH (s:Slip {code: $code})
                    OPTIONAL MATCH (s)-[rb:IN_DATA_BATCH]->(:CorpusBatch)
                    DELETE rb
                    """,
                    code=code,
                )
        else:
            tx.run(
                """
                MATCH (s:Slip {code: $code})
                OPTIONAL MATCH (s)-[rc:IN_CORPUS]->(:Corpus)
                DELETE rc
                OPTIONAL MATCH (s)-[rb:IN_DATA_BATCH]->(:CorpusBatch)
                DELETE rb
                """,
                code=code,
            )
    topics, persons, events = parse_slip_tags(tags)
    for t in topics:
        tx.run(
            """
            MATCH (s:Slip {code: $code})
            MERGE (tag:Tag {name: $tag})
            MERGE (s)-[:HAS_TAG]->(tag)
            """,
            code=code,
            tag=t,
        )
    for name in persons:
        tx.run(
            """
            MATCH (s:Slip {code: $code})
            MERGE (p:Person {name: $name})
            MERGE (s)-[:MENTIONS_PERSON]->(p)
            """,
            code=code,
            name=name,
        )
    for ev in events:
        tx.run(
            """
            MATCH (s:Slip {code: $code})
            MERGE (e:Event {name: $ename})
            MERGE (s)-[:RECORDS]->(e)
            """,
            code=code,
            ename=ev,
        )
        for name in persons:
            tx.run(
                """
                MATCH (e:Event {name: $ename})
                MERGE (p:Person {name: $pname})
                MERGE (e)-[:INVOLVES]->(p)
                """,
                ename=ev,
                pname=name,
            )


def _sync_slips_batch(driver, slips: List[Any], *, ensure_schema: bool = True) -> None:
    with driver.session() as session:
        if ensure_schema:
            _ensure_schema(session)

        def work(tx):
            for s in slips:
                _merge_slip_tx(tx, int(s.id), s.code, s.title, s.site_name, s.tags)

        session.execute_write(work)


def sync_bamboo_slips_from_mysql(limit: int | None = 500) -> Dict[str, Any]:
    """
    将 MySQL bamboo_slips 同步为 Neo4j 最小子图。
    limit 为正整数：单次最多同步该条数（上限 50_000）。
    limit 为 0 或 None：全库分批同步（每批 neo4j_batch_size 条，可重复执行，MERGE 幂等）。
    """
    from app.extensions import db
    from app.models import BambooSlip

    if limit is None or int(limit) <= 0:
        return sync_bamboo_slips_full_from_mysql()

    lim = max(1, min(int(limit), 50_000))

    slips = BambooSlip.query.order_by(BambooSlip.id.asc()).limit(lim).all()
    if not slips:
        return {"ok": True, "synced": 0, "message": "MySQL 中无简牍记录"}

    driver = None
    try:
        driver = _open_neo4j_driver()
        _sync_slips_batch(driver, slips, ensure_schema=True)
        return {"ok": True, "synced": len(slips), "limit": lim, "mode": "partial"}
    except Exception as e:
        return {"ok": False, "error": str(e), "synced": 0}
    finally:
        if driver is not None:
            driver.close()


def sync_bamboo_slips_full_from_mysql(batch_size: int | None = None) -> Dict[str, Any]:
    """全量同步：按批读取 MySQL 并写入 Neo4j，适合上线后与牍库一致。"""
    from app.extensions import db
    from app.models import BambooSlip

    bs = batch_size
    if bs is None:
        raw = current_app.config.get("NEO4J_SYNC_BATCH")
        try:
            bs = int(raw) if raw is not None else 2000
        except (TypeError, ValueError):
            bs = 2000
    bs = max(100, min(int(bs), 10_000))

    total = BambooSlip.query.count()
    if total == 0:
        return {"ok": True, "synced": 0, "message": "MySQL 中无简牍记录", "mode": "full"}

    driver = None
    synced = 0
    offset = 0
    try:
        driver = _open_neo4j_driver()
        first = True
        while True:
            slips = (
                BambooSlip.query.order_by(BambooSlip.id.asc()).offset(offset).limit(bs).all()
            )
            if not slips:
                break
            _sync_slips_batch(driver, slips, ensure_schema=first)
            first = False
            synced += len(slips)
            offset += len(slips)
            if len(slips) < bs:
                break
        return {"ok": True, "synced": synced, "total_in_mysql": total, "batch_size": bs, "mode": "full"}
    except Exception as e:
        return {"ok": False, "error": str(e), "synced": synced, "mode": "full"}
    finally:
        if driver is not None:
            driver.close()


def _trim_subgraph_edges(rows: List[Dict[str, Any]], max_nodes: int) -> List[Dict[str, Any]]:
    """从边列表中保留至多 max_nodes 个节点：自字典序最小的端点 BFS，再过滤边。"""
    if not rows or max_nodes <= 0:
        return []
    adj: Dict[str, List[str]] = {}
    for e in rows:
        s, t = e["source"], e["target"]
        adj.setdefault(s, []).append(t)
        adj.setdefault(t, []).append(s)
    start = min(adj.keys())
    seen: set[str] = set()
    dq: deque[str] = deque([start])
    seen.add(start)
    while dq:
        if len(seen) >= max_nodes:
            break
        u = dq.popleft()
        for v in adj.get(u, []):
            if v not in seen and len(seen) < max_nodes:
                seen.add(v)
                dq.append(v)
    return [e for e in rows if e["source"] in seen and e["target"] in seen]


def _pack_subgraph_from_edges(
    session, edges: List[Dict[str, Any]], lim: int
) -> Dict[str, Any]:
    """边列表 → BFS 截断 → 拉取节点属性（简牍带 slip_id / slip_code 供前端跳转）。"""
    if not edges:
        return {"nodes": [], "edges": [], "source": "neo4j"}
    trimmed = _trim_subgraph_edges(edges, lim)
    if not trimmed:
        return {"nodes": [], "edges": [], "source": "neo4j"}
    node_ids = sorted({e["source"] for e in trimmed} | {e["target"] for e in trimmed})
    nodes = session.run(
        """
        MATCH (n)
        WHERE elementId(n) IN $ids
        WITH labels(n)[0] AS label, n
        RETURN elementId(n) AS id, label,
               coalesce(n.name, n.title, n.code, toString(n.slip_id), toString(elementId(n))) AS name,
               n.code AS slip_code,
               n.slip_id AS slip_id
        """,
        ids=node_ids,
    ).data()
    out_nodes: List[Dict[str, Any]] = []
    for row in nodes:
        d: Dict[str, Any] = {
            "id": row["id"],
            "name": row["name"],
            "category": row["label"],
        }
        if row.get("label") == "Slip":
            sid = row.get("slip_id")
            if sid is not None:
                d["slip_id"] = int(sid)
            sc = row.get("slip_code")
            if sc:
                d["slip_code"] = sc
        out_nodes.append(d)
    return {
        "nodes": out_nodes,
        "edges": [
            {"source": e["source"], "target": e["target"], "rel": e["rel"]}
            for e in trimmed
        ],
        "source": "neo4j",
    }


# 隐藏「遗址」边时同时排除说明书 EXCAVATED_AT 与历史 AT_SITE
_CY_REL_FILTER = "AND ($inc_site OR NOT type(r) IN ('EXCAVATED_AT','AT_SITE'))"


def fetch_graph_subgraph(
    limit_nodes: int = 120,
    include_site_edges: bool = True,
    site: Optional[str] = None,
    tag: Optional[str] = None,
    slip_code: Optional[str] = None,
    slip_id: Optional[int] = None,
) -> Dict[str, Any]:
    """从关系抽样子图再按节点数截断；Neo4j 不可用时返回空图。

    include_site_edges=False 时排除 EXCAVATED_AT / AT_SITE，可减轻星形爆炸；
    不含对 IN_CORPUS / IN_DATA_BATCH / PART_OF 的过滤（DeepJiandu 等无遗址字段时由语料节点编联）。

    筛选（互斥优先级：简牍 > 遗址 > 标签 > 全局抽样）：
    - slip_code / slip_id：以该简牍为中心取一跳关系；
    - site：遗址名（精确匹配，可先填 MySQL site_name 同步到 Neo4j 的值）；
    - tag：标签名精确匹配，取带该标签的简牍及其发出的关系（上限 300 条简牍种子）。
    """
    lim = max(10, min(int(limit_nodes), 400))
    edge_limit = min(max(lim * 10, 80), 3000)
    inc_site = bool(include_site_edges)

    sc = (slip_code or "").strip()
    site_n = (site or "").strip()
    tag_n = (tag or "").strip()

    def _fallback_from_mysql() -> Dict[str, Any]:
        """Neo4j 不可用时，从 MySQL 现有字段拼一张最小可用图谱。"""
        lim2 = max(10, min(int(limit_nodes), 260))
        q = BambooSlip.query
        if slip_id is not None:
            q = q.filter(BambooSlip.id == int(slip_id))
        if sc:
            q = q.filter(BambooSlip.code == sc)
        if site_n:
            q = q.filter(BambooSlip.site_name == site_n)
        if tag_n:
            # 粗匹配：tags 为逗号分隔字符串
            q = q.filter(BambooSlip.tags.like(f"%{tag_n}%"))
        rows: List[BambooSlip] = q.order_by(BambooSlip.id.desc()).limit(lim2).all()

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        node_by_key: Dict[str, Dict[str, Any]] = {}

        def upsert_node(key: str, name: str, cat: str, **extra: Any) -> str:
            if key in node_by_key:
                return key
            d: Dict[str, Any] = {"id": key, "name": name, "category": cat}
            d.update(extra)
            node_by_key[key] = d
            nodes.append(d)
            return key

        def add_edge(src: str, tgt: str, rel: str) -> None:
            edges.append({"source": src, "target": tgt, "rel": rel})

        for s in rows:
            sk = f"slip:{s.id}"
            upsert_node(sk, f"{s.code} {s.title}".strip(), "Slip", slip_id=int(s.id), slip_code=s.code)
            if include_site_edges and s.site_name:
                site_key = f"site:{s.site_name}"
                upsert_node(site_key, s.site_name, "Site")
                add_edge(sk, site_key, "AT_SITE")
            raw_tags = (s.tags or "").strip()
            if raw_tags:
                parts = [p.strip() for p in raw_tags.replace("，", ",").split(",") if p.strip()]
                for t in parts[:12]:
                    # 人物与标签简单区分：支持「人:」「人物:」
                    if t.startswith("人:") or t.startswith("人物:") or t.startswith("人：") or t.startswith("人物："):
                        nm = t.split(":", 1)[-1].split("：", 1)[-1].strip()
                        if not nm:
                            continue
                        pk = f"person:{nm}"
                        upsert_node(pk, nm, "Person")
                        add_edge(sk, pk, "MENTIONS_PERSON")
                    else:
                        tk = f"tag:{t}"
                        upsert_node(tk, t, "Tag")
                        add_edge(sk, tk, "HAS_TAG")

        return {"nodes": nodes, "edges": edges, "source": "mysql_fallback"}

    driver = None
    try:
        driver = _open_neo4j_driver()
        with driver.session() as session:
            edges: List[Dict[str, Any]] = []
            site_edges_fallback = False

            if sc:
                q_slip = f"""
                    MATCH (s:Slip {{code: $sc}})
                    WITH s LIMIT 1
                    MATCH (s)-[r]-(o)
                    WHERE {_GRAPH_NODE_OR_O}
                      {_CY_REL_FILTER}
                    RETURN DISTINCT elementId(startNode(r)) AS source,
                                    elementId(endNode(r)) AS target, type(r) AS rel
                    LIMIT $el
                    """
                edges = session.run(
                    q_slip,
                    sc=sc,
                    el=edge_limit,
                    inc_site=inc_site,
                ).data()
                if not edges and not inc_site:
                    edges = session.run(
                        q_slip,
                        sc=sc,
                        el=edge_limit,
                        inc_site=True,
                    ).data()
                    site_edges_fallback = bool(edges)
            elif slip_id is not None:
                q_sid = f"""
                    MATCH (s:Slip)
                    WHERE s.slip_id = $sid
                    WITH s LIMIT 1
                    MATCH (s)-[r]-(o)
                    WHERE {_GRAPH_NODE_OR_O}
                      {_CY_REL_FILTER}
                    RETURN DISTINCT elementId(startNode(r)) AS source,
                                    elementId(endNode(r)) AS target, type(r) AS rel
                    LIMIT $el
                    """
                edges = session.run(
                    q_sid,
                    sid=int(slip_id),
                    el=edge_limit,
                    inc_site=inc_site,
                ).data()
                if not edges and not inc_site:
                    edges = session.run(
                        q_sid,
                        sid=int(slip_id),
                        el=edge_limit,
                        inc_site=True,
                    ).data()
                    site_edges_fallback = bool(edges)
            elif site_n:
                q_site = f"""
                    MATCH (site:Site)
                    WHERE site.name = $site_name
                    MATCH (s:Slip)-[sr]-(site)
                    WHERE type(sr) IN ('EXCAVATED_AT','AT_SITE')
                    WITH site, s
                    LIMIT 300
                    MATCH (s)-[r]->(o)
                    WHERE {_GRAPH_NODE_OR_O}
                      {_CY_REL_FILTER}
                    RETURN elementId(startNode(r)) AS source,
                           elementId(endNode(r)) AS target, type(r) AS rel
                    LIMIT $el
                    """
                edges = session.run(
                    q_site,
                    site_name=site_n,
                    el=edge_limit,
                    inc_site=inc_site,
                ).data()
                if not edges and not inc_site:
                    edges = session.run(
                        q_site,
                        site_name=site_n,
                        el=edge_limit,
                        inc_site=True,
                    ).data()
                    site_edges_fallback = bool(edges)
            elif tag_n:
                q_tag = f"""
                    MATCH (t:Tag)
                    WHERE t.name = $tag_name
                    MATCH (s:Slip)-[:HAS_TAG]->(t)
                    WITH t, s
                    LIMIT 300
                    MATCH (s)-[r]->(o)
                    WHERE {_GRAPH_NODE_OR_O}
                      {_CY_REL_FILTER}
                    RETURN elementId(startNode(r)) AS source,
                           elementId(endNode(r)) AS target, type(r) AS rel
                    LIMIT $el
                    """
                edges = session.run(
                    q_tag,
                    tag_name=tag_n,
                    el=edge_limit,
                    inc_site=inc_site,
                ).data()
                if not edges and not inc_site:
                    edges = session.run(
                        q_tag,
                        tag_name=tag_n,
                        el=edge_limit,
                        inc_site=True,
                    ).data()
                    site_edges_fallback = bool(edges)
            else:
                rel_extra = (
                    ""
                    if include_site_edges
                    else "AND NOT type(r) IN ('EXCAVATED_AT','AT_SITE')"
                )
                edges = session.run(
                    f"""
                    MATCH (a)-[r]->(b)
                    WHERE {_GRAPH_NODE_OR_A}
                      AND {_GRAPH_NODE_OR_B}
                      {rel_extra}
                    RETURN elementId(a) AS source, elementId(b) AS target, type(r) AS rel
                    LIMIT $el
                    """,
                    el=edge_limit,
                ).data()
                # 仅隐藏遗址边时，若图中主要只有「简牍—遗址」关系，会导致边被全部过滤为空。
                # 此时自动回退为包含遗址边，避免前端出现“空画布”。
                if not edges and not include_site_edges:
                    edges = session.run(
                        f"""
                        MATCH (a)-[r]->(b)
                        WHERE {_GRAPH_NODE_OR_A}
                          AND {_GRAPH_NODE_OR_B}
                        RETURN elementId(a) AS source, elementId(b) AS target, type(r) AS rel
                        LIMIT $el
                        """,
                        el=edge_limit,
                    ).data()
                    site_edges_fallback = bool(edges)

            packed = _pack_subgraph_from_edges(session, edges, lim)
            if site_edges_fallback:
                packed["site_edges_fallback"] = True
            return packed
    except Exception:
        try:
            return _fallback_from_mysql()
        except Exception:
            db.session.rollback()
            return {"nodes": [], "edges": [], "source": "unavailable"}
    finally:
        if driver is not None:
            driver.close()


def seed_hint_cypher() -> str:
    return """// 最小子图由后端从 MySQL 同步（管理端「Neo4j 同步」或 scripts/sync_neo4j_from_slips.py）
// 也可在 Browser 中手工种示例：
CREATE (s:Slip {code:'DEMO-001', slip_id: 1, title:'示例简牍'})
MERGE (t:Tag {name:'边塞'})
MERGE (p:Person {name:'李敢'})
MERGE (x:Site {name:'居延'})
MERGE (s)-[:HAS_TAG]->(t)
MERGE (s)-[:MENTIONS_PERSON]->(p)
MERGE (s)-[:EXCAVATED_AT]->(x)
MERGE (s)-[:AT_SITE]->(x);

// tags：人:姓名 → Person；事件:名称 → Event（RECORDS / INVOLVES）
// DeepJiandu 导入（code 以 DJ- 开头且无 site_name）同步时会自动出现：
//   (:Corpus {name:'DeepJiandu（影像语料）'})<-[:IN_CORPUS]-(:Slip)
//   及可选 (:CorpusBatch {key:'dj:train'}) 等，语义为数据集非考古遗址。
"""
