import os

from flask import Flask, request
from flask_cors import CORS

from app.config import get_config
from app.extensions import db, jwt, limiter


def create_app(config_overrides: dict | None = None):
    app = Flask(__name__)
    app.config.from_object(get_config())
    if config_overrides:
        app.config.update(config_overrides)

    limiter.init_app(app)

    @limiter.request_filter
    def _exempt_rate_limit():
        p = request.path or ""
        if p.startswith("/api/media/"):
            return True
        if p in ("/api/health", "/api/health/ready"):
            return True
        return False

    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
    )

    db.init_app(app)
    jwt.init_app(app)

    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.user_bp import bp as user_bp
    from app.blueprints.daily_slip import bp as daily_bp
    from app.blueprints.rag import bp as rag_bp
    from app.blueprints.graph import bp as graph_bp
    from app.blueprints.chat import bp as chat_bp
    from app.blueprints.posts import bp as posts_bp
    from app.blueprints.tasks import bp as tasks_bp
    from app.blueprints.recommend import bp as rec_bp
    from app.blueprints.misc import bp as misc_bp
    from app.blueprints.slips import bp as slips_bp
    from app.blueprints.analytics import bp as analytics_bp
    from app.blueprints.admin import bp as admin_bp
    from app.blueprints.media import bp as media_bp
    from app.blueprints.story import bp as story_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(user_bp, url_prefix="/api/user")
    app.register_blueprint(daily_bp, url_prefix="/api/daily-slip")
    app.register_blueprint(rag_bp, url_prefix="/api/rag")
    app.register_blueprint(graph_bp, url_prefix="/api/graph")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(posts_bp, url_prefix="/api/posts")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(rec_bp, url_prefix="/api/recommend")
    app.register_blueprint(misc_bp, url_prefix="/api")
    app.register_blueprint(slips_bp, url_prefix="/api/slips")
    app.register_blueprint(analytics_bp, url_prefix="/api/analytics")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(media_bp, url_prefix="/api/media")
    app.register_blueprint(story_bp, url_prefix="/api/story")

    with app.app_context():
        db.create_all()
        skip_chroma = os.getenv("SKIP_STARTUP_CHROMA_SYNC", "").strip().lower() in ("1", "true", "yes", "on")
        # 测试库与「仅关键词」模式都不在启动时加载嵌入模型。
        from app.constants import RAG_USE_CHROMA

        if app.config.get("TESTING") or not RAG_USE_CHROMA:
            skip_chroma = True
        if not skip_chroma:
            try:
                from app.services.rag_service import sync_slips_to_chroma_if_possible

                sync_slips_to_chroma_if_possible()
            except Exception:
                pass

    return app
