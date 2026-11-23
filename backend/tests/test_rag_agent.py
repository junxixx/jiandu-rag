from app.services.rag_agent import iterate_plan
from app.services.rag_fusion import rrf_fuse
from app.services.rag_keywords import _SIMP_TRAD, extract_keywords, keyword_hit


def test_trad_map_has_unique_simplified_chars():
    simplified = [a for a, _b in _SIMP_TRAD]
    assert len(simplified) == len(set(simplified))


def test_keyword_simplified_matches_traditional_text():
    assert keyword_hit("奉钱", "候長呂憲奉錢千二百")
    assert keyword_hit("候长", "候長呂憲")
    assert not keyword_hit("地铁", "候長呂憲奉錢千二百")


def test_mixed_script_name_matches_corpus():
    from app.services.rag_keywords import trad_variants

    variants = trad_variants("候长吕宪")
    assert "候長吕憲" in variants
    assert "候長呂憲" in variants
    assert keyword_hit("候长吕宪", "候長吕憲奉錢千二百")


def test_extract_keywords_drops_question_words():
    kws = extract_keywords("候长吕宪的奉钱是多少")
    assert "候长吕宪" in kws
    assert "奉钱" in kws
    assert "多少" not in kws


def test_rrf_overlap_ranks_first():
    keyword = [{"id": 1}, {"id": 2}, {"id": 3}]
    vector = [{"id": 2}, {"id": 4}, {"id": 1}]
    fused = rrf_fuse([("keyword", keyword), ("vector", vector)], rrf_k=60, top_n=3)
    assert fused[0]["id"] == 2
    paths = {item["path"] for item in fused[0]["sources"]}
    assert paths == {"keyword", "vector"}


def test_rrf_single_list_keeps_order():
    docs = [{"id": 8}, {"id": 3}, {"id": 5}]
    fused = rrf_fuse([("keyword", docs)], top_n=3)
    assert [item["id"] for item in fused] == [8, 3, 5]


def _events(question, retrieve, rewrite=None):
    return list(iterate_plan(question, retrieve, rewrite=rewrite, max_rewrites=2, top_k=3))


def test_chitchat_skips_retrieval():
    called = {"n": 0}

    def retrieve(_q):
        called["n"] += 1
        return []

    events = _events("你好", retrieve)
    assert called["n"] == 0
    assert events[-1]["plan"]["route"] == "chat"
    assert events[-1]["plan"]["refused"] is False
    assert any(ev.get("stage") == "chat" for ev in events)


def test_in_corpus_passes_without_rewrite():
    doc = {
        "id": 7,
        "code": "DJ-train-3264",
        "title": "简牍 DJ-train-3264",
        "transcription": "候長呂憲奉錢千二百",
        "vernacular": "",
    }

    def retrieve(q):
        kws = extract_keywords(q)
        if any(keyword_hit(kw, doc["transcription"]) for kw in kws):
            return [doc]
        return []

    events = _events("候长吕宪的奉钱是多少", retrieve)
    assert events[-1]["type"] == "ready"
    assert events[-1]["plan"]["refused"] is False
    assert events[-1]["plan"]["docs"][0]["code"] == "DJ-train-3264"
    assert not any(ev.get("stage") == "rewrite" for ev in events)


def test_out_of_corpus_refuses():
    def retrieve(_q):
        return []

    events = _events("今天上海地铁几号线经过陆家嘴", retrieve)
    assert events[-1]["type"] == "done"
    assert events[-1]["plan"]["refused"] is True
    assert any(ev.get("stage") == "refuse" for ev in events)
    assert not any(ev.get("type") == "ready" for ev in events)


def test_partial_miss_can_retry_then_pass():
    doc = {
        "id": 3,
        "code": "DJ-x",
        "title": "简",
        "transcription": "戍卒口粮三石",
        "vernacular": "",
    }
    calls = {"n": 0}

    def retrieve(_q):
        calls["n"] += 1
        if calls["n"] >= 2:
            return [doc]
        return []

    def rewrite(_question, _keywords, _attempt, _hits=0):
        return "口粮"

    events = _events("戍卒的口粮", retrieve, rewrite=rewrite)
    assert events[-1]["type"] == "ready"
    assert calls["n"] >= 2
    assert any(ev.get("stage") == "rewrite" for ev in events)
