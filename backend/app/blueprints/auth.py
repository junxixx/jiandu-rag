import secrets

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt_identity, jwt_required

from app.constants import POINTS_INVITE_NEWUSER, POINTS_INVITE_REFERRER
from app.extensions import db, limiter
from app.models import User

bp = Blueprint("auth", __name__)


@bp.post("/register")
@limiter.limit("12 per minute")
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    nickname = (data.get("nickname") or username or "青声同好").strip()
    invite_in = (data.get("invite_code") or "").strip().upper()
    if not username or not email or len(password) < 6:
        return jsonify({"error": "用户名、邮箱必填，密码至少6位"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "用户名已存在"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "邮箱已注册"}), 409
    ref = User.query.filter_by(invite_code=invite_in).first() if invite_in else None
    if invite_in and not ref:
        return jsonify({"error": "邀请码无效"}), 400
    u = User(username=username, email=email, nickname=nickname)
    if ref:
        u.referred_by_user_id = ref.id
    u.set_password(password)
    db.session.add(u)
    db.session.flush()
    for _ in range(8):
        code = secrets.token_hex(3).upper()[:8]
        if not User.query.filter_by(invite_code=code).first():
            u.invite_code = code
            break
    if ref:
        ref.points = (ref.points or 0) + POINTS_INVITE_REFERRER
        u.points = (u.points or 0) + POINTS_INVITE_NEWUSER
    db.session.commit()
    access = create_access_token(identity=str(u.id))
    refresh = create_refresh_token(identity=str(u.id))
    return (
        jsonify({"access_token": access, "refresh_token": refresh, "user": _user_public(u)}),
        201,
    )


@bp.post("/login")
@limiter.limit("20 per minute")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    u = User.query.filter_by(username=username).first()
    if not u or not u.check_password(password):
        return jsonify({"error": "用户名或密码错误"}), 401
    access = create_access_token(identity=str(u.id))
    refresh = create_refresh_token(identity=str(u.id))
    return jsonify({"access_token": access, "refresh_token": refresh, "user": _user_public(u)})


@bp.post("/refresh")
@jwt_required(refresh=True)
@limiter.limit("60 per minute")
def refresh():
    uid = get_jwt_identity()
    access = create_access_token(identity=str(uid))
    return jsonify({"access_token": access})


@bp.post("/logout")
@jwt_required()
def logout():
    """JWT 无状态：客户端丢弃 token 即可；此处占位便于前端统一调用。"""
    return jsonify({"ok": True})


def _user_public(u: User):
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "nickname": u.nickname,
        "avatar_url": u.avatar_url,
        "points": u.points,
        "invite_code": getattr(u, "invite_code", None),
    }
