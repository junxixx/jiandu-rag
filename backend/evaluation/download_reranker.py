"""从 ModelScope 下载 BAAI/bge-reranker-base，避开 Hugging Face 超时。"""

from pathlib import Path
import urllib.request

DEST = Path(__file__).resolve().parents[1] / "models" / "bge-reranker-base"
FILES = [
    "config.json",
    "model.safetensors",
    "sentencepiece.bpe.model",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
]
BASE = "https://www.modelscope.cn/models/BAAI/bge-reranker-base/resolve/master/"


def fetch(name: str) -> None:
    target = DEST / name
    if target.exists() and target.stat().st_size > 0:
        print(f"keep {name} {target.stat().st_size}")
        return
    DEST.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    print(f"get {name}")
    with urllib.request.urlopen(BASE + name, timeout=60) as response, partial.open("wb") as handle:
        total = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            total += len(chunk)
            if total % (64 * 1024 * 1024) < 1024 * 1024:
                print(f"  {name} {total / 1024 / 1024:.0f} MB", flush=True)
    partial.replace(target)
    print(f"done {name} {target.stat().st_size}")


if __name__ == "__main__":
    for filename in FILES:
        fetch(filename)
