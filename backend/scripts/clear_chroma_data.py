"""
删除本地 Chroma 持久化目录，用于更换 EMBEDDING_MODEL 后重建向量索引。

用法（在 backend 目录下）:
  python scripts/clear_chroma_data.py

然后重启 Flask（会自动 sync）或 POST /api/rag/reindex（需配置 ADMIN_TOKEN）。
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

_backend = Path(__file__).resolve().parents[1]
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_backend / ".env", override=True)

persist = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data").strip() or "./chroma_data"
path = Path(persist)
if not path.is_absolute():
    path = _backend / path

if path.exists():
    shutil.rmtree(path)
    print(f"已删除 Chroma 目录: {path}")
else:
    print(f"目录不存在（跳过）: {path}")

print("下一步：确认 .env 中 EMBEDDING_MODEL，然后重启后端或执行牍库 → Chroma 同步。")
