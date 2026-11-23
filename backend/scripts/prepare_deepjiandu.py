"""
DeepJiandu：官方 Pascal VOC 标注 + BMP 影像的导入说明。

请使用正式导入脚本（写入 bamboo_slips、可选同步 Chroma）:

  cd backend
  python scripts/import_deepjiandu.py --limit 50    # 试跑
  python scripts/import_deepjiandu.py --reindex      # 全量 + 向量库

目录约定见 import_deepjiandu.py 文件头注释；生产环境可将 image_url 换为 CDN 绝对地址。
"""
from __future__ import annotations


def main():
    print(__doc__)


if __name__ == "__main__":
    main()
