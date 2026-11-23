import os
import re

from flask import Blueprint, abort, current_app, send_from_directory

bp = Blueprint("media", __name__)

_SPLIT_OK = frozenset({"train", "val", "test"})
_NAME_OK = re.compile(r"^[A-Za-z0-9._-]+\.(bmp|png|jpg|jpeg)$", re.IGNORECASE)


@bp.get("/deepjiandu/<split>/<path:filename>")
def deepjiandu_image(split: str, filename: str):
    """提供 DeepJiandu 解压后的简牍影像（本地试运行）；生产可改 CDN 并不再走此路由。"""
    if split not in _SPLIT_OK or not _NAME_OK.match(filename or ""):
        abort(404)
    root = current_app.config.get("DEEPJIANDU_IMAGE_ROOT") or ""
    folder = os.path.join(root, split)
    if not os.path.isdir(folder):
        abort(404)
    full = os.path.join(folder, filename)
    if not os.path.isfile(full) or not os.path.abspath(full).startswith(os.path.abspath(folder)):
        abort(404)
    return send_from_directory(folder, filename, max_age=86400)
