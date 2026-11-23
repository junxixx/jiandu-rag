import json
from typing import Generator

import httpx
from flask import current_app


def _strip_md_bold_markers(text: str) -> str:
    """去掉模型常用的 Markdown 加粗标记 **，避免前端纯文本里露出星号。"""
    if not text:
        return text
    return text.replace("**", "")


def chat_completion(
    messages: list[dict],
    model: str = "deepseek-chat",
    temperature: float = 0.7,
    timeout: float = 120.0,
) -> str:
    cfg = current_app.config
    key = cfg.get("DEEPSEEK_API_KEY") or ""
    base = (cfg.get("DEEPSEEK_API_BASE", "https://api.deepseek.com") or "").rstrip("/")
    if not key:
        return "（未配置 DEEPSEEK_API_KEY，请在 .env 中设置后再试。）"

    url = f"{base}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    return _strip_md_bold_markers(data["choices"][0]["message"]["content"].strip())


def chat_completion_stream(
    messages: list[dict],
    model: str = "deepseek-chat",
    temperature: float = 0.3,
) -> Generator[str, None, None]:
    cfg = current_app.config
    key = cfg.get("DEEPSEEK_API_KEY") or ""
    base = (cfg.get("DEEPSEEK_API_BASE", "https://api.deepseek.com") or "").rstrip("/")
    if not key:
        yield "（未配置 DEEPSEEK_API_KEY。）"
        return
    url = f"{base}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=120.0) as client:
        with client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="ignore")
                if not line.startswith("data: "):
                    continue
                chunk = line[6:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    obj = json.loads(chunk)
                    delta = obj["choices"][0].get("delta") or {}
                    piece = delta.get("content") or ""
                    if piece:
                        yield _strip_md_bold_markers(piece)
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
