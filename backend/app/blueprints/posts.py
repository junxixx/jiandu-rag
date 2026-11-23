import json
import re

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.constants import AI_MODERATION_BLOCK, AI_MODERATION_PENDING, POINTS_POST_LIKE
from app.extensions import db
from app.models import Comment, Post, PostLike, Topic, User
from app.services import deepseek as ds
from app.services.site_config import get_extra_blocked_words

bp = Blueprint("posts", __name__)

BLOCK_WORDS = ("法轮", "赌博", "色情")


def _moderate_fast(text: str) -> tuple[bool, str]:
    t = text or ""
    for w in BLOCK_WORDS:
        if w in t:
            return False, "内容包含敏感词"
    for w in get_extra_blocked_words():
        if w and w in t:
            return False, "内容包含敏感词"
    if len(t) > 8000:
        return False, "内容过长"
    return True, ""


def _ai_moderate(text: str) -> tuple[float, list]:
    """说明书：DeepSeek 返回 risk_score / labels。"""
    if len(text) < 20:
        return 0.0, []
    try:
        raw = ds.chat_completion(
            [
                {
                    "role": "system",
                    "content": "你是内容风控助手。只输出一行合法 JSON："
                    '{"risk_score":0到1的小数,"labels":["标签"]}，不要其它文字。',
                },
                {"role": "user", "content": (text or "")[:3500]},
            ],
            temperature=0.05,
        )
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return 0.0, []
        obj = json.loads(m.group())
        return float(obj.get("risk_score", 0)), list(obj.get("labels") or [])
    except Exception:
        return 0.0, []


def _status_from_risk(score: float) -> str:
    if score >= AI_MODERATION_BLOCK:
        return "blocked"
    if score >= AI_MODERATION_PENDING:
        return "pending"
    return "published"


def _maybe_ai_summary(content: str) -> str | None:
    if len(content) < 200:
        return None
    if not content.strip():
        return None
    try:
        return ds.chat_completion(
            [
                {
                    "role": "system",
                    "content": "你是问牍雅集的录事。请用100字以内中文概括下列帖子要点，平实客观。",
                },
                {"role": "user", "content": content[:6000]},
            ],
            temperature=0.2,
        )
    except Exception:
        return None


@bp.get("")
def list_posts():
    page = int(request.args.get("page", 1))
    size = min(int(request.args.get("size", 20)), 50)
    topic_id = request.args.get("topic_id", type=int)
    q = Post.query.filter(Post.status == "published")
    if topic_id:
        q = q.filter_by(topic_id=topic_id)
    q = q.order_by(Post.created_at.desc())
    total = q.count()
    rows = q.offset((page - 1) * size).limit(size).all()
    return jsonify(
        {
            "total": total,
            "items": [
                {
                    "id": p.id,
                    "title": p.title,
                    "summary": p.ai_summary,
                    "author": p.author.nickname if p.author else "",
                    "likes_count": p.likes_count,
                    "topic_id": p.topic_id,
                    "topic_name": p.topic.name if p.topic_id and p.topic else None,
                    "created_at": p.created_at.isoformat(),
                }
                for p in rows
            ],
        }
    )


@bp.post("")
@jwt_required()
def create_post():
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()[:256]
    content = (data.get("content") or "").strip()
    topic_id = data.get("topic_id")
    ok, err = _moderate_fast(title + content)
    if not ok:
        return jsonify({"error": err}), 400
    risk, labels = _ai_moderate(title + "\n" + content)
    status = _status_from_risk(risk)
    summary = _maybe_ai_summary(content) if status != "blocked" else None
    p = Post(
        user_id=uid,
        title=title or "无标题",
        content=content,
        ai_summary=summary,
        topic_id=int(topic_id) if topic_id else None,
        status=status,
        risk_score=risk,
        moderation_labels=labels,
    )
    db.session.add(p)
    if p.topic_id:
        t = Topic.query.get(p.topic_id)
        if t:
            t.post_count = (t.post_count or 0) + 1
    db.session.commit()
    try:
        from app.services import badge_service as bs

        if status == "published":
            bs.after_first_post(uid)
    except Exception:
        pass
    return jsonify({"id": p.id, "ai_summary": summary, "status": p.status, "risk_score": risk}), 201


@bp.get("/<int:pid>")
def get_post(pid):
    p = Post.query.get(pid)
    if not p or p.status != "published":
        return jsonify({"error": "帖子不存在"}), 404
    cs = (
        Comment.query.filter_by(post_id=pid).order_by(Comment.created_at.asc()).limit(100).all()
    )
    topic_name = None
    if p.topic_id and p.topic:
        topic_name = p.topic.name
    return jsonify(
        {
            "id": p.id,
            "title": p.title,
            "content": p.content,
            "ai_summary": p.ai_summary,
            "likes_count": p.likes_count,
            "author": p.author.nickname if p.author else "",
            "topic_id": p.topic_id,
            "topic_name": topic_name,
            "created_at": p.created_at.isoformat(),
            "comments": [
                {
                    "id": c.id,
                    "content": c.content,
                    "author": c.author.nickname if c.author else "",
                    "created_at": c.created_at.isoformat(),
                }
                for c in cs
            ],
        }
    )


@bp.post("/<int:pid>/comments")
@jwt_required()
def add_comment(pid):
    uid = int(get_jwt_identity())
    p = Post.query.get(pid)
    if not p:
        return jsonify({"error": "帖子不存在"}), 404
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    ok, err = _moderate_fast(content)
    if not ok:
        return jsonify({"error": err}), 400
    if not content:
        return jsonify({"error": "内容不能为空"}), 400
    c = Comment(post_id=pid, user_id=uid, content=content[:4000])
    db.session.add(c)
    db.session.commit()
    return jsonify({"id": c.id}), 201


@bp.post("/<int:pid>/like")
@jwt_required()
def like_post(pid):
    uid = int(get_jwt_identity())
    p = Post.query.get(pid)
    if not p or p.status != "published":
        return jsonify({"error": "帖子不存在"}), 404
    ex = PostLike.query.filter_by(post_id=pid, user_id=uid).first()
    if ex:
        return jsonify({"liked": True, "likes_count": p.likes_count})
    db.session.add(PostLike(post_id=pid, user_id=uid))
    p.likes_count = (p.likes_count or 0) + 1
    u = User.query.get(uid)
    if u:
        u.points = (u.points or 0) + POINTS_POST_LIKE
    db.session.commit()
    return jsonify({"liked": True, "likes_count": p.likes_count})


@bp.post("/<int:pid>/ai-debate")
@jwt_required()
def ai_debate_on_post(pid):
    """话题帖下 AI 辩论员：结合帖文与用户立场驳难。"""
    uid = int(get_jwt_identity())
    p = Post.query.get(pid)
    if not p or p.status != "published":
        return jsonify({"error": "帖子不存在"}), 404
    data = request.get_json(silent=True) or {}
    side = (data.get("side") or "正方").strip()
    user_arg = (data.get("argument") or "").strip()
    if not user_arg:
        return jsonify({"error": "argument 不能为空"}), 400
    ctx = f"帖子标题：{p.title}\n摘要：{p.ai_summary or ''}\n正文节选：{p.content[:1200]}"
    system = (
        f"这是一场围绕帖文内容的简牍文化辩论。用户代表{side}。"
        "请结合帖子观点与简牍常识作两到三段反驳，语气克制。"
    )
    reply = ds.chat_completion(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": f"{ctx}\n\n用户论点：{user_arg}"},
        ],
        temperature=0.55,
    )
    try:
        from app.services import badge_service as bs

        bs.after_debate(uid)
    except Exception:
        pass
    return jsonify({"rebuttal": reply})
