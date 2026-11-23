from app.services.rag_metrics import first_relevant_rank, hit_at_k, reciprocal_rank
from app.services.rag_rerank import order_by_scores


def test_hit_and_mrr_use_gold_slip_code():
    rank = first_relevant_rank(["DJ-a", "DJ-b", "DJ-gold"], ["DJ-gold"])
    assert rank == 3
    assert hit_at_k(rank, 5)
    assert reciprocal_rank(rank, 5) == 1 / 3
    assert not hit_at_k(first_relevant_rank(["DJ-a"], ["DJ-gold"]), 5)
    assert reciprocal_rank(6, 5) == 0.0


def test_rerank_order_follows_score():
    docs = [
        {"id": 1, "code": "DJ-low", "sources": [{"path": "keyword", "rank": 1}]},
        {"id": 2, "code": "DJ-high", "sources": [{"path": "vector", "rank": 4}]},
    ]
    ordered = order_by_scores(docs, [0.1, 2.4], top_n=1)
    assert ordered[0]["code"] == "DJ-high"
    assert ordered[0]["rerank_score"] == 2.4
    assert ordered[0]["sources"][-1] == {"path": "rerank", "rank": 1}
