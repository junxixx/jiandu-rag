"""
DeepJiandu VOC：仅使用各 object 的 <name> 字类标签（html 实体已解码），
按框几何位置做「自右向左分列、列内自上而下」串联，供牍库释文字段。

说明：数据集中无单独「整句释文」字段；本模块不做「仅按 ymin 一锅端」式拼接。
"""
from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple


CharBox = Tuple[str, int, int, int, int]  # ch, ymin, xmin, xmax, ymax


def parse_voc_char_boxes(xml_path: Path) -> tuple[str, List[CharBox]]:
    """解析 VOC，返回 (影像文件名, 字框列表)。"""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    filename = (root.findtext("filename") or "").strip()
    if not filename:
        raise ValueError(f"缺少 filename: {xml_path}")
    rows: List[CharBox] = []
    for obj in root.findall("object"):
        name_el = obj.find("name")
        if name_el is None or not (name_el.text or "").strip():
            continue
        bb = obj.find("bndbox")
        if bb is None:
            continue
        try:
            ymin = int(bb.findtext("ymin") or "0")
            xmin = int(bb.findtext("xmin") or "0")
            xmax = int(bb.findtext("xmax") or "0")
            ymax = int(bb.findtext("ymax") or "0")
        except ValueError:
            continue
        ch = html.unescape((name_el.text or "").strip())
        if ch:
            rows.append((ch, ymin, xmin, xmax, ymax))
    return filename, rows


def transcription_from_label_boxes(chars: List[CharBox]) -> str:
    """
    仅用各框的「标签字」与坐标：自右向左分列，列内按 ymin 自上而下串联。
    列宽阈值取字框宽度中位数，避免与仅按 ymin 全局排序混同。
    """
    if not chars:
        return ""
    items: list[tuple[str, int, float, int, int]] = []
    widths: list[int] = []
    xcs: list[float] = []
    for ch, ymin, xmin, xmax, ymax in chars:
        w = max(1, xmax - xmin)
        widths.append(w)
        xc = (xmin + xmax) / 2.0
        xcs.append(xc)
        items.append((ch, ymin, xc, xmin, xmax))
    med_w = sorted(widths)[len(widths) // 2]
    min_xc = min(xcs)
    max_xc = max(xcs)
    # 列间距：与字宽相关；全幅过窄时退化为单列
    wband = max(24.0, min(float(med_w) * 1.35, max(80.0, (max_xc - min_xc) / 8.0 + med_w)))

    from collections import defaultdict

    cols: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for ch, ymin, xc, _xmin, _xmax in items:
        cid = int((max_xc - xc) / wband)
        cols[cid].append((ch, ymin))

    parts: list[str] = []
    for cid in sorted(cols.keys()):
        col_chars = sorted(cols[cid], key=lambda t: t[1])
        parts.append("".join(t[0] for t in col_chars))
    return "".join(parts)
