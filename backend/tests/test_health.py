def test_health_returns_json(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("app")
    assert "status" in data
    assert "checks" in data


def test_health_ready_sqlite(client):
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    assert r.get_json().get("ready") is True
