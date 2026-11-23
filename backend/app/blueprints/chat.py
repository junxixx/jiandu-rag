from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.chat_roles import ROLE_LABELS, ROLE_PROMPTS, VALID_ROLE_KEYS, NIGHT_CHAT_ROLES
from app.extensions import db, limiter
from app.models import ChatMessage, ChatSession, User
from app.services import deepseek as ds
from app.services import redis_chat as rc

bp = Blueprint("chat", __name__)


@bp.get("/roles")
def list_roles():
    """夜话可选人物（前端建席、首页卡片与之一致）。"""
    return jsonify(
        {
            "items": [
                {
                    "role_key": r["role_key"],
                    "label": r["label"],
                    "card_title": r["card_title"],
                    "hint": r["hint"],
                }
                for r in NIGHT_CHAT_ROLES
            ]
        }
    )


@bp.post("/sessions")
@jwt_required()
def create_session():
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    mode = (data.get("mode") or "single").strip().lower()
    title = (data.get("title") or "边塞对话").strip()[:128]
    if mode == "group":
        raw_keys = data.get("role_keys") or ["li_gan", "shang_guan"]
        keys = [str(k).strip() for k in raw_keys if str(k).strip() in VALID_ROLE_KEYS][:3]
        if len(keys) < 2:
            keys = ["li_gan", "ban_chao"]
        s = ChatSession(
            user_id=uid,
            role_key=keys[0],
            title=title or "群儒夜话",
            chat_mode="group",
            group_roles_json=keys,
        )
    else:
        role_key = (data.get("role_key") or "li_gan").strip()
        if role_key not in VALID_ROLE_KEYS:
            role_key = "li_gan"
        s = ChatSession(user_id=uid, role_key=role_key, title=title, chat_mode="single")
    db.session.add(s)
    db.session.commit()
    return (
        jsonify(
            {
                "id": s.id,
                "role_key": s.role_key,
                "title": s.title,
                "chat_mode": s.chat_mode,
                "group_roles": s.group_roles_json,
            }
        ),
        201,
    )


@bp.get("/sessions")
@jwt_required()
def list_sessions():
    uid = int(get_jwt_identity())
    rows = (
        ChatSession.query.filter_by(user_id=uid)
        .order_by(ChatSession.created_at.desc())
        .limit(30)
        .all()
    )
    return jsonify(
        {
            "items": [
                {
                    "id": r.id,
                    "role_key": r.role_key,
                    "title": r.title,
                    "chat_mode": getattr(r, "chat_mode", "single") or "single",
                    "group_roles": getattr(r, "group_roles_json", None),
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        }
    )


@bp.get("/sessions/<int:sid>/messages")
@jwt_required()
def history(sid):
    uid = int(get_jwt_identity())
    s = ChatSession.query.get(sid)
    if not s or s.user_id != uid:
        return jsonify({"error": "会话不存在"}), 404
    rows = (
        ChatMessage.query.filter_by(session_id=sid).order_by(ChatMessage.created_at.asc()).limit(200).all()
    )
    return jsonify(
        {
            "items": [
                {"role": r.role, "content": r.content, "created_at": r.created_at.isoformat()}
                for r in rows
            ]
        }
    )


@bp.post("/sessions/<int:sid>/messages")
@jwt_required()
@limiter.limit("40 per minute")
def send(sid):
    uid = int(get_jwt_identity())
    s = ChatSession.query.get(sid)
    if not s or s.user_id != uid:
        return jsonify({"error": "会话不存在"}), 404
    data = request.get_json(silent=True) or {}
    text = (data.get("content") or "").strip()
    if not text:
        return jsonify({"error": "content 不能为空"}), 400

    um = ChatMessage(session_id=sid, role="user", content=text)
    db.session.add(um)
    db.session.commit()

    sk = f"u{uid}:s{sid}"
    rc.append_turn(sk, "user", text, user_id=uid, role_key=s.role_key)

    if (getattr(s, "chat_mode", "single") or "single") == "group":
        roles = s.group_roles_json or ["li_gan", "shang_guan"]
        replies_out = []
        hist = rc.recent_turns(sk, 10)
        for rk in roles:
            system = ROLE_PROMPTS.get(rk, ROLE_PROMPTS["li_gan"])
            msgs = [{"role": "system", "content": system}]
            for role, content in hist:
                if role == "user":
                    msgs.append({"role": "user", "content": content})
                else:
                    msgs.append({"role": "assistant", "content": content})
            if not msgs[-1:] or msgs[-1].get("role") != "user":
                msgs.append({"role": "user", "content": text})
            reply = ds.chat_completion(msgs, temperature=0.75)
            label = ROLE_LABELS.get(rk, rk)
            chunk = f"【{label}】{reply}"
            db.session.add(ChatMessage(session_id=sid, role="assistant", content=chunk))
            replies_out.append({"role_key": rk, "label": label, "reply": reply})
            rc.append_turn(sk, "assistant", chunk, user_id=uid, role_key=rk)
        db.session.commit()
        return jsonify({"replies": replies_out, "mode": "group"})

    system = ROLE_PROMPTS.get(s.role_key, ROLE_PROMPTS["li_gan"])
    msgs = [{"role": "system", "content": system}]
    for role, content in rc.recent_turns(sk, 10):
        if role == "user":
            msgs.append({"role": "user", "content": content})
        else:
            msgs.append({"role": "assistant", "content": content})
    if not msgs[-1:] or msgs[-1].get("role") != "user":
        msgs.append({"role": "user", "content": text})

    reply = ds.chat_completion(msgs, temperature=0.8)
    am = ChatMessage(session_id=sid, role="assistant", content=reply)
    db.session.add(am)
    db.session.commit()
    rc.append_turn(sk, "assistant", reply, user_id=uid, role_key=s.role_key)

    return jsonify({"reply": reply, "mode": "single"})
