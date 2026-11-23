"""从当前牍库抽出 40 道带标准简号的检索题。相关简号是释文里真正含答案片段的那几支。"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
load_dotenv(BACKEND / ".env")
sys.path.insert(0, str(BACKEND))

from app import create_app
from app.models import BambooSlip
from app.services.rag_keywords import _SIMP_TRAD

_TO_SIMP = {trad: simp for simp, trad in _SIMP_TRAD}
_PARTICLES = set("的与和及或在对从把被为以中里之而则并跟同向到至")
SEEDS = [
    ("候长吕宪的奉钱是多少", "候長吕憲奉錢千二百"),
    ("长安到茂陵有多远", "長安至茂陵七十里"),
    ("月氏到乌氏多少里", "月氏至烏氏五十里"),
    ("乌氏到泾阳多少里", "烏氏至涇陽五十里"),
    ("居延置到鲽里有多远", "居延置至鰈裏九十里"),
    ("夫人付给奉世多少干饭", "夫人付奉世干飯"),
    ("临木隧长徐忠的奉钱", "臨木隧長徐忠奉錢"),
    ("建昭五年十月谁在付奉钱", "建昭五年十月丙寅"),
    ("阳绀叩头记了什么", "陽紺叩足頭"),
    ("尊取牛肠记了多少", "尊取牛腸"),
]


def to_simplified(text: str) -> str:
    return "".join(_TO_SIMP.get(ch, ch) for ch in text)


def usable_window(text: str) -> bool:
    if len(text) < 8 or "□" in text or len(set(text)) < 6:
        return False
    return not any(ch in _PARTICLES for ch in text[:4])


def main() -> None:
    app = create_app()
    with app.app_context():
        slips = [
            (row.code, row.transcription or "")
            for row in BambooSlip.query.with_entities(BambooSlip.code, BambooSlip.transcription).all()
        ]
    owners8: dict[str, set[str]] = defaultdict(set)
    owners4: dict[str, set[str]] = defaultdict(set)
    for code, text in slips:
        compact = "".join((text or "").split())
        seen8: set[str] = set()
        seen4: set[str] = set()
        for index in range(0, max(0, len(compact) - 7)):
            window = compact[index : index + 8]
            if window not in seen8 and usable_window(window):
                seen8.add(window)
                owners8[window].add(code)
            prefix = compact[index : index + 4]
            if len(prefix) == 4 and prefix not in seen4 and "□" not in prefix:
                seen4.add(prefix)
                owners4[prefix].add(code)

    items = []
    used_codes: set[str] = set()

    def add(question: str, span: str, codes: set[str]) -> None:
        if not codes or len(codes) > 8:
            print(f"skip\t{question}\tmatches={len(codes)}")
            return
        primary = sorted(codes)[0]
        if primary in used_codes and len(items) >= 10:
            return
        used_codes.add(primary)
        items.append(
            {
                "id": f"r-{len(items) + 1:02d}",
                "question": question,
                "expect_codes": sorted(codes),
                "answer_span": span,
            }
        )

    for question, span in SEEDS:
        add(question, span, set(owners8.get(span, set())) or {code for code, text in slips if span in text})

    by_prefix: dict[str, tuple[str, set[str]]] = {}
    for window, codes in owners8.items():
        if not (1 <= len(codes) <= 3):
            continue
        prefix = window[:4]
        breadth = len(owners4.get(prefix, ()))
        if breadth < 4:
            continue
        if any(code in used_codes for code in codes):
            continue
        current = by_prefix.get(prefix)
        if current is None or breadth > current[0]:
            by_prefix[prefix] = (breadth, window, codes)  # type: ignore[assignment]
    ranked_prefixes = sorted(by_prefix.values(), key=lambda item: -item[0])
    for _breadth, window, codes in ranked_prefixes:
        if len(items) >= 40:
            break
        add(to_simplified(window), window, codes)

    if len(items) < 40:
        raise SystemExit(f"只找到 {len(items)} 题，不足 40")
    payload = {
        "note": "expect_codes 是释文含 answer_span 的简号。问句只暴露更常见的前四字或一句白话，不用整段释文当答案。",
        "items": items[:40],
    }
    (HERE / "eval_ranking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(payload['items'])} items")
    for item in payload["items"]:
        print(f"{item['id']}\t{item['question']}\t{item['expect_codes']}\t{item['answer_span']}")


if __name__ == "__main__":
    main()
