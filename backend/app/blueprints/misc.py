import json
import os
import re

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import text
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.extensions import db, limiter
from app.models import Badge, Topic
from app.services import deepseek as ds
from app.services import site_config as sc

bp = Blueprint("misc", __name__)

_DEFAULT_DEBATE_TOPICS = [
    "简牍数字化是否应优先于原件整理发表",
    "边塞简牍能否单独支撑一部「大众史」",
    "AI 释读简牍是否会削弱传统文字学训练",
    "公众考古热度是否会稀释简牍研究的严肃性",
    "简牍释文是否应在未定字处保留更多「存疑」而非强行隶定",
    "出土简牍能否作为中学历史教材的主干史料",
    "私人收藏简牍影像的流通边界应如何划定",
    "机器转写与人工隶定：何者更应作为学术引用的底本",
    "简牍数据库的「开放获取」与文物信息安全如何平衡",
]

_DEBATE_PERSONA = {
    "master": "你是一位博通简牍与秦汉魏晋出土文献的「牍师」，驳难时兼顾制度、字形与史地常识。",
    "clerk": "你是一位熟谙律令与文书体式的「刀笔吏」，驳难时偏重牒式、术语与行政程序是否自洽。",
    "soldier": "你以熟悉边塞戍务的「烽燧戍卒」视角，可从禀食、候望、徭役、烽次等实务切入。",
}

_DEBATE_INTENSITY = {
    "mild": "驳难以梳理概念、澄清前提为主，点到为止，少用尖锐措辞。",
    "standard": "在尊重对方的前提下，指出论证跳跃或史料运用不当之处。",
    "sharp": "可直指核心薄弱环节与概念混淆，仍须保持礼数，不作人身攻击。",
}


def _parse_debate_reply(text: str) -> tuple[str, str]:
    """解析模型输出的【沉吟】…【驳辞】…；失败则全文视为驳辞。"""
    if not text:
        return "", ""
    s = text.strip()
    if "【驳辞】" in s:
        parts = s.split("【驳辞】", 1)
        head = parts[0].replace("【沉吟】", "").strip()
        tail = parts[1].strip() if len(parts) > 1 else ""
        if head.startswith("：") or head.startswith(":"):
            head = head[1:].strip()
        return head, tail or s
    return "", s


def _normalize_prior_turns(raw) -> list[dict]:
    """[{user, rebuttal}, ...] 只保留字符串字段。"""
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for t in raw[-12:]:
        if not isinstance(t, dict):
            continue
        u = str(t.get("user") or "").strip()
        r = str(t.get("rebuttal") or "").strip()
        if u or r:
            out.append({"user": u[:6000], "rebuttal": r[:6000]})
    return out


def _format_prior_turns_for_prompt(turns: list[dict], max_chars: int = 10000) -> str:
    if not turns:
        return "（尚无先前轮次）"
    chunks: list[str] = []
    for i, t in enumerate(turns, start=1):
        u = t.get("user") or ""
        r = t.get("rebuttal") or ""
        chunks.append(f"——第{i}轮——\n【持方申述】\n{u}\n【牍师驳辞】\n{r}\n")
    s = "\n".join(chunks)
    if len(s) <= max_chars:
        return s
    tail = s[-max_chars:]
    return "……（更早轮次从略）……\n" + tail


def _debate_system_base(persona_key: str, intensity_key: str) -> tuple[str, float]:
    persona_line = _DEBATE_PERSONA.get(persona_key, _DEBATE_PERSONA["master"])
    intensity_line = _DEBATE_INTENSITY.get(intensity_key, _DEBATE_INTENSITY["standard"])
    temps = {"mild": 0.55, "standard": 0.62, "sharp": 0.68}
    temperature = temps.get(intensity_key, 0.62)
    return f"{persona_line}\n{intensity_line}", temperature


def _output_format_instruction() -> str:
    return (
        "请严格按下列两段输出（保留【沉吟】【驳辞】四字标记作为行首，其后直接接正文，勿加小标题）：\n"
        "【沉吟】用不超过70字、略带古韵的白话，写你在落笔前的一两句内心斟酌（不用引号）。\n"
        "【驳辞】"
    )


@bp.get("/health")
def health():
    mysql_ok = False
    try:
        db.session.execute(text("SELECT 1"))
        mysql_ok = True
    except Exception:
        db.session.rollback()
    root = (current_app.config.get("DEEPJIANDU_IMAGE_ROOT") or "").strip()
    test_dir = os.path.join(root, "test") if root else ""
    deepjiandu_ok = bool(root and os.path.isdir(test_dir))
    status = "ok" if mysql_ok else "degraded"
    return jsonify(
        {
            "status": status,
            "app": "问牍·青声",
            "tagline": "简牍为纸，青年为墨",
            "checks": {"mysql": mysql_ok, "deepjiandu_test_dir": deepjiandu_ok},
        }
    )


@bp.get("/health/ready")
def health_ready():
    """编排就绪探针：数据库不可用则 503。"""
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"ready": True}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"ready": False}), 503


@bp.get("/public/topics")
def topics_public():
    """雅集话题列表（发帖可选 topic_id）。"""
    rows = Topic.query.order_by(Topic.hot.desc(), Topic.id.asc()).limit(50).all()
    return jsonify(
        {
            "items": [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "post_count": t.post_count,
                    "hot": t.hot,
                }
                for t in rows
            ]
        }
    )


@bp.post("/share-copy-suggestions")
@limiter.limit("30 per minute")
def share_copy_suggestions():
    """分享牍卡等场景：DeepSeek 生成 2～3 条短文案备选（说明书 F4.4）。"""
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "简牍一叶").strip()[:128]
    snippet = (data.get("snippet") or "").strip()[:500]
    try:
        raw = ds.chat_completion(
            [
                {
                    "role": "system",
                    "content": "输出恰好3条适合发朋友圈的简牍分享语，每句不超过40字，"
                    "文雅克制。只输出 JSON 数组，如 [\"...\",\"...\",\"...\"]",
                },
                {"role": "user", "content": f"标题：{title}\n摘录：{snippet}"},
            ],
            temperature=0.75,
        )
        m = re.search(r"\[[\s\S]*\]", raw)
        if m:
            arr = json.loads(m.group())
            if isinstance(arr, list):
                lines = [str(x).strip() for x in arr if str(x).strip()][:3]
                if lines:
                    return jsonify({"lines": lines})
    except Exception:
        pass
    return jsonify(
        {
            "lines": [
                f"在读：{title}",
                "边塞墨迹，青年共读——问牍·青声",
                "一枚木牍，一段两千年前的日常。",
            ]
        }
    )


@bp.get("/public/badges")
def badges_catalog():
    rows = Badge.query.order_by(Badge.id.asc()).all()
    return jsonify(
        {
            "items": [
                {
                    "code": r.code,
                    "title": r.title,
                    "description": r.description,
                    "icon": r.icon,
                }
                for r in rows
            ]
        }
    )


@bp.get("/public/debate-topics")
def debate_topics_public():
    extra = sc.get_debate_topics()
    items = extra if extra else _DEFAULT_DEBATE_TOPICS
    return jsonify({"items": items})


@bp.post("/debate")
@limiter.limit("24 per minute")
def debate():
    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "简牍是否应优先数字化公开").strip()
    side = (data.get("side") or "正方").strip()
    user_arg = (data.get("argument") or "").strip()
    phase = (data.get("phase") or "open").strip().lower()
    if phase not in ("open", "continue", "yield", "conclude"):
        phase = "open"
    persona_key = (data.get("persona") or "master").strip().lower()
    if persona_key not in _DEBATE_PERSONA:
        persona_key = "master"
    intensity_key = (data.get("intensity") or "standard").strip().lower()
    if intensity_key not in _DEBATE_INTENSITY:
        intensity_key = "standard"
    base_sys, temperature = _debate_system_base(persona_key, intensity_key)
    prior_turns = _normalize_prior_turns(data.get("prior_turns"))
    fmt = _output_format_instruction()

    if phase == "open":
        if not user_arg:
            return jsonify({"error": "argument 不能为空"}), 400
        system = (
            f"{base_sys}\n"
            f"这是一场围绕简牍与出土文献的辩论，辩题：{topic}。用户代表{side}。"
            "用户消息为其首轮立论全文。\n"
            f"{fmt}"
            "用两到四段话正式反驳用户论点，可引用简牍制度、文书格式、西北汉简或边塞行政常识，"
            "语气克制有礼，避免空泛口号与绝对化断言。"
        )
        user_message = user_arg
    elif phase == "continue":
        if not user_arg:
            return jsonify({"error": "续论 argument 不能为空"}), 400
        if not prior_turns:
            return jsonify({"error": "continue 须携带 prior_turns（至少一轮交锋）"}), 400
        ctx = _format_prior_turns_for_prompt(prior_turns)
        system = (
            f"{base_sys}\n"
            f"这是一场围绕简牍与出土文献的多轮辩论，辩题：{topic}。用户代表{side}。\n"
            "以下为此前各轮交锋（用户申述与牍师驳辞交替）。\n"
            f"{ctx}\n"
            "【当前轮】用户在上一轮驳辞之后提交如下续论或申辩。请针对其新论点、新例证或对你旧驳辞的回应，再次驳难；"
            "不可简单重复首轮措辞，可承认其合理处再转折。\n"
            f"{fmt}"
            "驳辞仍两到四段。"
        )
        user_message = user_arg
    elif phase == "yield":
        ctx = _format_prior_turns_for_prompt(prior_turns) if prior_turns else "（本场尚无交锋记录）"
        system = (
            f"{base_sys}\n"
            f"辩题：{topic}。用户原代表{side}。\n"
            f"{ctx}\n"
            "用户现已明言认输、甘拜下风或愿闻指教（其最后一言见用户消息，可为空）。\n"
            f"{fmt}"
            "驳辞限两段以内：大度勉励、回扣辩题与治学提醒，不可讥讽挖苦，不作居高临下之训。"
        )
        user_message = user_arg or "（未附言，仅以认输告。）"
    else:  # conclude
        ctx = _format_prior_turns_for_prompt(prior_turns) if prior_turns else "（本场尚无交锋记录）"
        system = (
            f"{base_sys}\n"
            f"辩题：{topic}。用户原代表{side}。\n"
            f"{ctx}\n"
            "用户请求鸣金收兵、友好结束本场辩论（其最后一言见用户消息，可为空）。\n"
            f"{fmt}"
            "驳辞限两段以内：简要小结双方论旨、致谢切磋，可点出尚待深究的一两个问题，语气平和收束。"
        )
        user_message = user_arg or "（未附言，仅以鸣金告。）"

    reply = ds.chat_completion(
        [{"role": "system", "content": system}, {"role": "user", "content": user_message}],
        temperature=temperature,
    )
    thinking, rebuttal_body = _parse_debate_reply(reply)
    if not rebuttal_body:
        rebuttal_body = reply.strip()
    try:
        verify_jwt_in_request(optional=True)
        raw = get_jwt_identity()
        if raw:
            from app.services import badge_service as bs

            bs.after_debate(int(raw))
    except Exception:
        pass
    return jsonify(
        {
            "thinking": thinking,
            "rebuttal": rebuttal_body,
            "persona": persona_key,
            "intensity": intensity_key,
            "phase": phase,
        }
    )


@bp.post("/quick-read")
@limiter.limit("24 per minute")
def quick_read():
    data = request.get_json(silent=True) or {}
    slip_text = (data.get("transcription") or "").strip()
    if not slip_text:
        return jsonify({"error": "transcription 不能为空"}), 400
    system = (
        "你是「问牍·青声」的讲牍人。把下列简牍释文改写成约三分钟可读完的短故事，"
        "保留人名、官职、地点与数字等关键信息，语气亲切如向同好夜话，勿加戏说离谱情节。"
    )
    story = ds.chat_completion(
        [{"role": "system", "content": system}, {"role": "user", "content": slip_text[:4000]}],
        temperature=0.7,
    )
    return jsonify({"story": story})
