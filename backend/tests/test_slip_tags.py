from app.utils.slip_tags import append_person, format_slip_tags, normalize_slip_tags, parse_slip_tags


def test_parse_mixed():
    t, p, e = parse_slip_tags("边塞,屯戍,人:张安世")
    assert t == ["边塞", "屯戍"]
    assert p == ["张安世"]
    assert e == []


def test_parse_fullwidth_colon():
    t, p, e = parse_slip_tags("人物：王五")
    assert p == ["王五"]
    assert t == []
    assert e == []


def test_format_canonical_person():
    s = format_slip_tags(["A", "B"], ["张三"])
    assert s == "A,B,人:张三"


def test_normalize_dedupe():
    s = normalize_slip_tags("人:李,人：李,边塞,边塞")
    assert s == "边塞,人:李"


def test_append_person():
    s = append_person("边塞", "赵六")
    assert s == "边塞,人:赵六"
