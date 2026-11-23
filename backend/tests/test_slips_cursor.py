def test_slips_cursor_mode_returns_has_more(client):
    r = client.get("/api/slips?after_id=0&size=2")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data
    assert data.get("total") is None
    assert "has_more" in data
    assert isinstance(data["has_more"], bool)
