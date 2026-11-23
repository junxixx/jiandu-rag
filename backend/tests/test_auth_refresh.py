def test_refresh_returns_new_access_token(client, app):
    with app.app_context():
        from flask_jwt_extended import create_refresh_token

        rt = create_refresh_token(identity="1")

    r = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {rt}"})
    assert r.status_code == 200
    body = r.get_json()
    assert "access_token" in body
