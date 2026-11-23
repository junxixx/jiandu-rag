from datetime import timedelta

import pytest
from sqlalchemy.pool import StaticPool

from app import create_app
from app.extensions import db


@pytest.fixture
def app():
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            },
            "JWT_ACCESS_TOKEN_EXPIRES": timedelta(minutes=120),
            "JWT_REFRESH_TOKEN_EXPIRES": timedelta(days=7),
            "RATELIMIT_ENABLED": False,
        }
    )
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
