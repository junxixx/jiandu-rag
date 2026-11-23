"""说明书对齐的积分与业务常量（可 .env 覆盖）。"""
import os

POINTS_READ_SLIP = int(os.getenv("POINTS_READ_SLIP", "10"))
POINTS_SHARE_CARD = int(os.getenv("POINTS_SHARE_CARD", "15"))
POINTS_QUIZ_CORRECT = int(os.getenv("POINTS_QUIZ_CORRECT", "20"))
POINTS_POST_LIKE = int(os.getenv("POINTS_POST_LIKE", "1"))
POINTS_INVITE_REFERRER = int(os.getenv("POINTS_INVITE_REFERRER", "30"))
POINTS_INVITE_NEWUSER = int(os.getenv("POINTS_INVITE_NEWUSER", "30"))
POINTS_CHECKIN_BASE = int(os.getenv("POINTS_CHECKIN_BASE", "5"))
# 连续打卡第 7 天起积分倍数（仅作用于当日打卡奖励）
STREAK_BONUS_MULTIPLIER_DAYS = int(os.getenv("STREAK_BONUS_MULTIPLIER_DAYS", "7"))
STREAK_BONUS_MULTIPLIER = float(os.getenv("STREAK_BONUS_MULTIPLIER", "2.0"))

RAG_TOP_K = max(1, min(int(os.getenv("RAG_TOP_K", "5")), 20))
RAG_HYDE = os.getenv("RAG_HYDE", "0").strip().lower() in ("1", "true", "yes", "on")
# 为 0 时问牍仅用 MySQL 关键词检索，不加载 Chroma/本地嵌入模型（避免首请求拉 HF 权重卡死）
RAG_USE_CHROMA = os.getenv("RAG_USE_CHROMA", "0").strip().lower() in ("1", "true", "yes", "on")
RAG_RRF_K = max(1, int(os.getenv("RAG_RRF_K", "60")))
RAG_MAX_REWRITES = max(0, min(int(os.getenv("RAG_MAX_REWRITES", "2")), 4))
# 每一路先召回这么多，再融合；开启重排时对这 20 条打分，最后留 RAG_TOP_K 条
RAG_POOL = max(RAG_TOP_K, min(int(os.getenv("RAG_POOL", "20")), 40))
RAG_USE_RERANK = os.getenv("RAG_USE_RERANK", "0").strip().lower() in ("1", "true", "yes", "on")
RAG_RERANK_MODEL = os.getenv("RAG_RERANK_MODEL", "BAAI/bge-reranker-base")

AI_MODERATION_BLOCK = float(os.getenv("AI_MODERATION_BLOCK", "0.7"))
AI_MODERATION_PENDING = float(os.getenv("AI_MODERATION_PENDING", "0.3"))
