"""
将 DeepJiandu 标注（Pascal VOC XML）与对应 .bmp 影像导入 MySQL bamboo_slips，并可选同步 Chroma。

目录约定（与官方压缩包一致）:
  <项目根>/DeepJiandu_labels/DeepJiandu_labels/{train,val,test}/*.xml
  <项目根>/DeepJiandu/{train,val,test}/*.bmp
XML 中 <object><name> 为字类标签（可含 &#xxxx; 实体）；释文仅由各框该标签与框坐标生成：
按自右向左分列、列内自上而下串联（见 app.utils.deepjiandu_transcription），不做「仅按 ymin 一锅端」式拼接。

tags：无真实主题时可留空；人物、遗址请在库内改 tags（「人:姓名」等）后跑 Neo4j 同步。
出土地 site_name：本数据集不含考古出土地信息时不写入（勿用数据集名称冒充遗址）。
同步 Neo4j 后，后端会为 DJ- 前缀简牍自动挂上「影像语料」Corpus 节点（非遗址），便于图谱编联。

用法（在 backend 目录，已配置 .env 与数据库）:
  python scripts/import_deepjiandu.py --limit 200
  python scripts/import_deepjiandu.py
  python scripts/import_deepjiandu.py --reindex

生产 CDN：使用 --image-url-prefix https://cdn.example.com/static/deepjiandu 写入绝对地址；
  或导入后用 SQL 批量替换 image_url。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _backend)

# 须在 import app 之前加载 .env，否则 config 里 SQLALCHEMY_DATABASE_URI 会用空密码固化
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_backend, ".env"), override=True)
os.environ.setdefault("SKIP_STARTUP_CHROMA_SYNC", "1")

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import BambooSlip  # noqa: E402
from app.utils.deepjiandu_transcription import (  # noqa: E402
    parse_voc_char_boxes,
    transcription_from_label_boxes,
)
from app.utils.slip_tags import format_slip_tags  # noqa: E402


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_voc_xml(xml_path: Path) -> tuple[str, str]:
    """兼容旧调用：返回 (filename, 依字类标签与读序规则生成的释文串)。"""
    filename, boxes = parse_voc_char_boxes(xml_path)
    return filename, transcription_from_label_boxes(boxes)


def find_image(images_root: Path, split: str, filename: str) -> Path | None:
    p = images_root / split / filename
    if p.is_file():
        return p
    return None


def main() -> None:
    repo = _repo_root()
    default_labels = repo / "DeepJiandu_labels" / "DeepJiandu_labels"
    default_images = repo / "DeepJiandu"

    ap = argparse.ArgumentParser(description="导入 DeepJiandu XML+BMP 到 bamboo_slips")
    ap.add_argument("--labels-root", type=Path, default=default_labels, help="含 train/val/test 的 XML 根目录")
    ap.add_argument("--images-root", type=Path, default=default_images, help="含 train/val/test 的影像根目录")
    ap.add_argument("--limit", type=int, default=0, help="最多处理条数，0 表示不限制")
    ap.add_argument("--reindex", action="store_true", help="导入后执行 Chroma 同步")
    ap.add_argument("--dry-run", action="store_true", help="只打印统计不写库")
    ap.add_argument(
        "--image-url-prefix",
        type=str,
        default="",
        help="非空时 image_url = {prefix}/{split}/{filename}；默认用 /api/media/deepjiandu/...",
    )
    args = ap.parse_args()

    if not args.labels_root.is_dir():
        print(f"标注目录不存在: {args.labels_root}")
        sys.exit(1)
    if not args.images_root.is_dir():
        print(f"影像目录不存在: {args.images_root}")
        sys.exit(1)

    app = create_app()
    processed = 0
    skipped_no_img = 0
    skipped_empty = 0
    updated = 0
    inserted = 0

    xml_files: list[tuple[str, Path]] = []
    for split in ("train", "val", "test"):
        d = args.labels_root / split
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.xml")):
            xml_files.append((split, p))

    with app.app_context():
        for split, xml_path in xml_files:
            if args.limit and processed >= args.limit:
                break
            try:
                filename, transcription = parse_voc_xml(xml_path)
            except Exception as e:
                print(f"跳过解析失败 {xml_path}: {e}")
                continue
            if not transcription:
                skipped_empty += 1
                continue
            img = find_image(args.images_root, split, filename)
            if not img:
                skipped_no_img += 1
                continue

            stem = Path(filename).stem
            code = f"DJ-{split}-{stem}"
            prefix = (args.image_url_prefix or "").strip().rstrip("/")
            if prefix:
                image_url = f"{prefix}/{split}/{filename}"
            else:
                image_url = f"/api/media/deepjiandu/{split}/{filename}"
            title = f"简牍 {code}"
            vernacular = (
                "【DeepJiandu 字类标签串联】\n"
                + transcription
                + "\n\n正式学术引用请以整理本或原简考释为准。"
            )

            processed += 1
            if args.dry_run:
                continue

            row = BambooSlip.query.filter_by(code=code).first()
            if row:
                row.title = title
                row.transcription = transcription
                row.vernacular = vernacular
                row.image_url = image_url
                row.site_name = None
                row.era = None
                row.tags = format_slip_tags([], [])
                updated += 1
            else:
                db.session.add(
                    BambooSlip(
                        code=code,
                        title=title,
                        image_url=image_url,
                        transcription=transcription,
                        vernacular=vernacular,
                        site_name=None,
                        era=None,
                        tags=format_slip_tags([], []),
                    )
                )
                inserted += 1

            if processed % 200 == 0 and not args.dry_run:
                db.session.commit()
                print(f"…已提交 {processed} 条")

        if not args.dry_run:
            db.session.commit()

        if args.reindex and not args.dry_run:
            from app.services.rag_service import sync_slips_to_chroma_if_possible

            r = sync_slips_to_chroma_if_possible()
            print("Chroma:", r)

    print(
        f"完成: 处理 {processed} 条（跳过无图 {skipped_no_img}，空释文 {skipped_empty}）；"
        f"新增 {inserted}，更新 {updated}；dry_run={args.dry_run}"
    )


if __name__ == "__main__":
    main()