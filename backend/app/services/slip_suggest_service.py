"""简牍详情页「猜你想问」：生成 3 条可点击的问牍提示。"""

from __future__ import annotations

import json
import re
from typing import List

from app.models import BambooSlip
from app.services import deepseek as ds


def suggested_questions_for_slip(slip: BambooSlip) -> List[str]:
    ctx = (
        f"编号：{slip.code}\n标题：{slip.title}\n释文节选：{slip.transcription[:600]}\n"
        f"白话节选：{slip.vernacular[:400]}"
    )
    try:
        raw = ds.chat_completion(
            [
                {
                    "role": "system",
                    "content": "你是简牍导读。根据材料生成恰好3个用户可能想深入问的问题，"
                    "每句不超过28字，不要编号，不要引号。只输出 JSON 数组，例如 "
                    '["问题1","问题2","问题3"]',
                },
                {"role": "user", "content": ctx},
            ],
            temperature=0.45,
        )
        m = re.search(r"\[[\s\S]*\]", raw)
        if m:
            arr = json.loads(m.group())
            if isinstance(arr, list):
                out = [str(x).strip() for x in arr if str(x).strip()][:3]
                if len(out) == 3:
                    return out
    except Exception:
        pass
    return _fallback(slip)


def _fallback(slip: BambooSlip) -> List[str]:
    site = slip.site_name or "该批简牍"
    return [
        f"「{slip.code}」主要记载什么内容？",
        f"「{site}」出土的简牍常见哪些文书类型？",
        "释文中的关键词若见于其他边塞简，制度上有何联系？",
    ]
