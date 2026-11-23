"""
模型与 prompt 抽检：列出本仓库内 LLM 调用位置，便于运营/合规走查。

不自动调用外网 API；仅输出清单与配置摘要。

用法（backend 目录）:
  python scripts/prompt_audit.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), override=True)

os.environ.setdefault("SKIP_STARTUP_CHROMA_SYNC", "1")

from app import create_app  # noqa: E402

ENTRIES = [
    ("边塞夜话人设", "app/blueprints/chat.py", "ROLE_PROMPTS（李敢 / 刀笔吏）"),
    ("问牍 RAG 非流式", "app/services/rag_service.py", "answer_with_rag system 提示"),
    ("问牍 RAG 流式", "app/services/rag_service.py", "stream_answer_with_rag system 提示"),
    ("RAG HyDE 扩写", "app/services/rag_service.py", "_hyde_query_text 内 system"),
    ("帖文 AI 摘要", "app/blueprints/posts.py", "_maybe_ai_summary"),
    ("帖文风控 JSON", "app/blueprints/posts.py", "_ai_moderate"),
    ("雅集 AI 辩论", "app/blueprints/posts.py", "ai_debate_on_post"),
    ("分享文案", "app/blueprints/misc.py", "share_copy_suggestions"),
    ("辩论社", "app/blueprints/misc.py", "debate"),
    ("快读成文", "app/blueprints/misc.py", "quick_read"),
    ("牍库联想", "app/services/slip_suggest_service.py", "chat_completion system"),
]


def main() -> None:
    app = create_app()
    print("—— Prompt / LLM 抽检清单（改文案请到对应文件）——\n")
    for title, path, note in ENTRIES:
        print(f"- {title}")
        print(f"    文件: {path}")
        print(f"    说明: {note}\n")

    with app.app_context():
        cfg = app.config
        print("—— 运行配置摘要（抽检时核对模型与密钥环境）——")
        print(f"  DEEPSEEK_API_BASE = {cfg.get('DEEPSEEK_API_BASE', '')}")
        key = cfg.get("DEEPSEEK_API_KEY") or ""
        print(f"  DEEPSEEK_API_KEY = {'已配置' if key else '未配置'}")
        print(f"  EMBEDDING_MODEL = {cfg.get('EMBEDDING_MODEL', '')}")
        print(f"  CHROMA_PERSIST_DIR = {cfg.get('CHROMA_PERSIST_DIR', '')}")
        print(f"  RAG_TOP_K / RAG_HYDE 见 app.constants（.env 可覆盖）")


if __name__ == "__main__":
    main()
