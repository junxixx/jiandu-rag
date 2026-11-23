"""用当前安装的 Chroma 和本地 bge-m3 重建向量库。旧库打不开，不能拿来检索。"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
load_dotenv(BACKEND / ".env")
sys.path.insert(0, str(BACKEND))

import chromadb
from sentence_transformers import SentenceTransformer

from app import create_app
from app.models import BambooSlip

DEST = BACKEND / "chroma_data_v2"
BATCH = 32


def main() -> None:
    if DEST.exists():
        shutil.rmtree(DEST)
    app = create_app()
    with app.app_context():
        rows = (
            BambooSlip.query.with_entities(
                BambooSlip.id,
                BambooSlip.code,
                BambooSlip.title,
                BambooSlip.transcription,
                BambooSlip.vernacular,
                BambooSlip.site_name,
            )
            .order_by(BambooSlip.id.asc())
            .all()
        )
    print(f"slips {len(rows)}", flush=True)
    model = SentenceTransformer(os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"), device="cpu")
    client = chromadb.PersistentClient(path=str(DEST))
    collection = client.get_or_create_collection(name="bamboo_slips", metadata={"hnsw:space": "cosine"})
    for start in range(0, len(rows), BATCH):
        chunk = rows[start : start + BATCH]
        docs = [
            f"{row.title}\n释文：{row.transcription}\n白话：{row.vernacular}\n遗址：{row.site_name or ''}"
            for row in chunk
        ]
        vectors = model.encode(docs, normalize_embeddings=False).tolist()
        collection.add(
            ids=[str(row.id) for row in chunk],
            embeddings=vectors,
            documents=[doc[:2000] for doc in docs],
            metadatas=[{"code": row.code, "title": row.title} for row in chunk],
        )
        print(f"upsert {start + len(chunk)}/{len(rows)}", flush=True)
    probe = model.encode(["候长吕宪的奉钱"], normalize_embeddings=False).tolist()
    found = collection.query(query_embeddings=probe, n_results=3, include=["metadatas"])
    print("probe", found.get("ids"), found.get("metadatas"), flush=True)


if __name__ == "__main__":
    main()
