import os
from datetime import timedelta

# 项目根目录（backend 的上一级），用于默认 DeepJiandu 影像路径
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_REPO_ROOT = os.path.abspath(os.path.join(_BACKEND_DIR, ".."))


def _jwt_access_expires():
    """JWT_ACCESS_MINUTES 留空或 0 表示访问令牌永不过期（仅建议本地演示）。"""
    raw = os.getenv("JWT_ACCESS_MINUTES", "").strip()
    if not raw or raw == "0":
        return False
    return timedelta(minutes=max(1, int(raw)))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = _jwt_access_expires()
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=max(1, int(os.getenv("JWT_REFRESH_DAYS", "30"))))

    # Flask-Limiter：生产可设为 REDIS_URL 同源，多实例共享计数
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "120 per minute")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{os.getenv('MYSQL_USER', 'root')}:"
        f"{os.getenv('MYSQL_PASSWORD', '')}@"
        f"{os.getenv('MYSQL_HOST', '127.0.0.1')}:"
        f"{os.getenv('MYSQL_PORT', '3306')}/"
        f"{os.getenv('MYSQL_DATABASE', 'dujian_youth')}"
        "?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
    NEO4J_SYNC_BATCH = max(100, min(int(os.getenv("NEO4J_SYNC_BATCH", "2000")), 10_000))

    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com").rstrip("/")

    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

    # 简易管理端：请求头 X-Admin-Token 须与此一致；留空则管理接口全部 403
    ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()

    # DeepJiandu 影像根目录（其下应有 train/ val/ test/ 子目录）。生产可换 CDN，DB 里存绝对 URL。
    DEEPJIANDU_IMAGE_ROOT = os.getenv(
        "DEEPJIANDU_IMAGE_ROOT",
        os.path.join(_REPO_ROOT, "DeepJiandu"),
    )

    # 牍库检索：在 MySQL 建好 FULLTEXT（见 scripts/optimize_slips_mysql.sql）后设为 1，可避免大表上多列 LIKE。
    SLIPS_USE_FULLTEXT = os.getenv("SLIPS_USE_FULLTEXT", "0").strip().lower() in ("1", "true", "yes", "on")
    # Chroma 同步时每批条数，避免一次性 upsert 过大占满内存
    CHROMA_UPSERT_BATCH = max(32, min(int(os.getenv("CHROMA_UPSERT_BATCH", "256")), 2000))


class DevelopmentConfig(Config):
    DEBUG = True


def get_config():
    env = os.getenv("FLASK_ENV", "development")
    return DevelopmentConfig if env == "development" else Config
