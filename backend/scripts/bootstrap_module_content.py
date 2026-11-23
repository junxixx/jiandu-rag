"""
补齐「每日一牍 / 雅集论道 / 边塞夜话」的演示内容。

适用场景：
- 已从别处导入 bamboo_slips，但未配置 daily_slips → 每日一牍 404 或陈旧
- 雅集尚无帖子 → 列表为空
- 边塞夜话左侧无会话 → 需用户手动「新开一席」；本脚本可为首位用户预置一条欢迎会话

前提：
- MySQL 库已迁移，且 bamboo_slips 中至少有一条简牍
- 雅集帖子需要至少一名已注册用户（请先在前台注册或使用已有账号）
- 建议在 backend 目录执行，并避免启动时全量 Chroma：
  set SKIP_STARTUP_CHROMA_SYNC=1
  python scripts/bootstrap_module_content.py

可选参数（默认全开）：
  python scripts/bootstrap_module_content.py --daily-only
  python scripts/bootstrap_module_content.py --forum-only
  python scripts/bootstrap_module_content.py --chat-only
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), override=True)

os.environ.setdefault("SKIP_STARTUP_CHROMA_SYNC", "1")

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import BambooSlip, ChatMessage, ChatSession, DailySlip, Post, Topic, User  # noqa: E402


def ensure_daily() -> str:
    slip = BambooSlip.query.order_by(BambooSlip.id.asc()).first()
    if not slip:
        return "跳过每日一牍：bamboo_slips 为空，请先导入简牍或运行 python scripts/seed_demo.py（空库时）。"

    today = date.today()
    row = DailySlip.query.filter_by(feature_date=today).first()
    if row:
        return f"每日一牍：今日 {today.isoformat()} 已有记录（daily_slip_id={row.id}），跳过。"

    row = DailySlip(
        slip_id=slip.id,
        feature_date=today,
        quiz_question="「禀食」类简牍主要反映以下哪类事务？",
        quiz_options=["军事训练", "口粮发放", "祭祀活动", "商业贸易"],
        correct_index=1,
    )
    db.session.add(row)
    db.session.commit()
    return f"每日一牍：已为 {today.isoformat()} 创建记录，关联简牍 id={slip.id}（{slip.code}）。"


def ensure_forum() -> str:
    user = User.query.order_by(User.id.asc()).first()
    if not user:
        return "跳过雅集：尚无注册用户，请先在前台「注册入册」后再运行本脚本。"

    published = Post.query.filter_by(status="published").count()
    if published >= 14:
        return f"雅集：已有 {published} 条已发布帖，跳过（阈值≥14）。"

    topics = Topic.query.order_by(Topic.id.asc()).limit(30).all()
    topic_by_name = {t.name: t for t in topics}

    samples = [
        ("边塞生活", "居延禀食简里的「小石」是多少？", "最近在牍库翻到几枚禀食简，想请教大家「小石」与「大石」的换算在学界通常怎么理解？"),
        ("考古揭秘", "简牍脱水与拍照顺序", "参观库房时听到两种说法，想听听做过整理的老师经验。"),
        ("读牍心得", "「候长」与「士吏」谁大？", "读候长文书时经常和士吏并提，职级关系想确认一下。"),
        ("书法艺术", "隶草之间：一枚残简的笔势", "放一张模糊图求指点笔顺，纯属学习交流。"),
        ("边塞生活", "烽燧轮值若是三天一班？", "想结合简牍里的更卒制度写个小短文，求拍砖。"),
        ("文书制度", "「诣官」与「自言」在简里怎么区分？", "看材料时两处用语都有，想厘清使用场景。"),
        ("法律与爰书", "爰书里常见套话有哪些？", "初学听辞类简，想记一点高频句式。"),
        ("名籍与算赋", "算赋在简牍里能直接看到吗？", "还是多从史书里反推？求指路。"),
        ("汉代历史", "王莽时期年号在简上怎么写？", "有没有常见写法或避讳例子？"),
        ("简牍整理", "缀合时怎么避免硬拼？", "有没有推荐的步骤或检查清单？"),
        ("数字化与开放", "简牍影像分辨率一般定多少？", "兼顾阅览与存储的经验想了解一下。"),
        ("民族与西域", "悬泉置简里的译使怎么理解？", "和一般传舍文书有何不同？"),
        ("比较视野", "木牍和竹简在书法上差异大吗？", "同一人手书有没有对照研究？"),
        ("读书会", "本周共读：禀食名籍", "下周想集中讨论几枚典型简，欢迎带问题来。"),
    ]

    n = 0
    for topic_name, short_title, body in samples:
        if Post.query.filter_by(title=short_title).first():
            continue
        tid = None
        t = topic_by_name.get(topic_name)
        if t:
            tid = t.id
        p = Post(
            user_id=user.id,
            topic_id=tid,
            title=short_title,
            content=body,
            status="published",
            likes_count=0,
        )
        db.session.add(p)
        n += 1
        if t:
            t.post_count = (t.post_count or 0) + 1

    db.session.commit()
    if n == 0:
        return "雅集：未新增（可能标题已存在或已达阈值）。"
    return f"雅集：已发布演示帖 {n} 条（作者 user_id={user.id}）。"


def ensure_chat() -> str:
    user = User.query.order_by(User.id.asc()).first()
    if not user:
        return "跳过边塞夜话：尚无注册用户。"

    if ChatSession.query.filter_by(user_id=user.id).first():
        return "边塞夜话：该用户已有会话记录，跳过预置。"

    s = ChatSession(
        user_id=user.id,
        role_key="li_gan",
        title="戍卒李敢",
        chat_mode="single",
    )
    db.session.add(s)
    db.session.flush()
    opener = (
        "在下李敢，居延塞上戍卒也。月色入户，正可闲话——君可问禀食、烽燧、文书体式，"
        "敢当尽力答之。（此为演示开场，续谈请点下方传书。）"
    )
    db.session.add(ChatMessage(session_id=s.id, role="assistant", content=opener))
    db.session.commit()
    return f"边塞夜话：已为首位用户（id={user.id}）预置会话「{s.title}」及开场白。"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily-only", action="store_true")
    ap.add_argument("--forum-only", action="store_true")
    ap.add_argument("--chat-only", action="store_true")
    args = ap.parse_args()
    all_default = not (args.daily_only or args.forum_only or args.chat_only)

    app = create_app()
    with app.app_context():
        msgs: list[str] = []
        if all_default or args.daily_only:
            msgs.append(ensure_daily())
        if all_default or args.forum_only:
            msgs.append(ensure_forum())
        if all_default or args.chat_only:
            msgs.append(ensure_chat())
        for m in msgs:
            print(m)


if __name__ == "__main__":
    main()
